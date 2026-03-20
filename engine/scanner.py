"""
Module engine/scanner.py
Scan vectorisé NumPy de toutes les combinaisons de trade-up valides.

Le scanner identifie les trade-ups avec EV positive en parcourant :
  - Tous les skins avec prix d'achat disponible
  - Tous les outputs possibles depuis tradeup_pool
  - Filtres configurables par utilisateur (ROI, budget, pool, liquidité)
"""

import json
import logging
from dataclasses import dataclass

import numpy as np

from data.database import get_session
from data.models import Opportunity, Price, Skin, TradeupPool
from engine.ev_calculator import InputSkin, OutputSkin, calculate_ev

logger = logging.getLogger(__name__)


@dataclass
class UserFilters:
    min_roi: float = 10.0
    max_budget: float = 200.0              # spec §4.3 : défaut 200 €
    max_pool_size: int = 5
    min_liquidity: float = 3.0
    min_volume_sell_price: int = 30        # ventes min pour fiabilité statistique (plage 10–100)
    exclude_trending_down: bool = False    # exclure outputs en baisse > 15% sur 30 jours
    exclude_high_volatility: bool = False  # exclure outputs avec variation 24h > 15%
    min_kontract_score: float = 0.0        # filtre composite Kontract Score
    min_volume_input: float = 1.0          # liquidité minimum de l'input (ventes/j)
    min_quantity_input: int = 10           # quantité minimum disponible pour exécution
    source_buy: str = "skinport"
    source_sell: str = "skinport"


def _get_platform_prices(session, platform: str) -> dict[str, dict]:
    """Retourne un dict skin_id → {buy_price, sell_price, volume_24h, …, median_7d, avg_7d, …}."""
    rows = session.query(Price).filter_by(platform=platform).all()
    return {
        r.skin_id: {
            "buy_price":  r.buy_price,
            "sell_price": r.sell_price,
            "volume_24h": r.volume_24h or 0.0,
            "volume_7d":  r.volume_7d  or 0.0,
            "volume_30d": r.volume_30d or 0.0,
            "quantity":   r.quantity,
            "median_price": r.sell_price,  # on utilise sell_price comme référence
            "median_24h": r.median_24h,
            "median_7d":  r.median_7d,
            "median_30d": r.median_30d,
            "median_90d": r.median_90d,
            "avg_24h":    r.avg_24h,
            "avg_7d":     r.avg_7d,
            "avg_30d":    r.avg_30d,
            "avg_90d":    r.avg_90d,
        }
        for r in rows
        if r.buy_price or r.sell_price
    }


def _get_output_pool(session, skin_id: str, collection_id: str) -> list[str]:
    """Retourne la liste des output_skin_id pour un input donné."""
    rows = session.query(TradeupPool).filter_by(
        input_skin_id=skin_id, collection_id=collection_id
    ).all()
    return [r.output_skin_id for r in rows]


def is_price_anomaly(min_price: float, median_price: float) -> bool:
    """
    Détecte un min_price anormal vs la médiane (spec §4.4).
    Retourne True si le prix doit être ignoré, fallback sur médiane.
    """
    if not median_price or median_price == 0:
        return True
    ratio = min_price / median_price
    return ratio < 0.5 or ratio > 2.0


def check_input_liquidity(
    quantity: int | None,
    buy_price: float | None = None,
    median_price: float | None = None,
    qty_needed: int = 10,
) -> dict:
    """
    Évalue la liquidité des inputs et retourne une estimation du prix unitaire
    corrigé selon la profondeur du carnet d'ordres (spec §4.5).

    Retourne : {
        'status': 'out_of_stock' | 'scarce' | 'partial' | 'liquid',
        'estimated_unit_price': float | None,
    }

    - liquid  (qty ≥ qty_needed) : médiane × qty — estimation conservatrice
    - partial (qty ≥ qty_needed//2) : interpolation (min + médiane) / 2
    - scarce  (qty < qty_needed//2) : médiane × 1.20 — pénalité 20%
    - None    : quantité inconnue → permissif, on garde le buy_price reçu
    """
    if quantity is None:
        return {"status": "liquid", "estimated_unit_price": buy_price}
    if quantity == 0:
        return {"status": "out_of_stock", "estimated_unit_price": None}

    if quantity >= qty_needed:
        return {"status": "liquid", "estimated_unit_price": median_price or buy_price}
    if quantity >= qty_needed // 2:
        if buy_price and median_price:
            est = (buy_price + median_price) / 2
        else:
            est = buy_price or median_price
        return {"status": "partial", "estimated_unit_price": est}
    # scarce
    base = median_price or buy_price or 0.0
    return {"status": "scarce", "estimated_unit_price": base * 1.20}


def validate_tradeup(skins: list) -> tuple[bool, str]:
    """
    Vérifie que la composition des inputs est valide selon les règles Valve (spec §4.4).
    Inclut la règle Covert post-octobre 2025 : 5 inputs seulement pour rarity_ancient_weapon.
    """
    stattrak_vals = {getattr(s, 'stattrak', False) for s in skins}
    if len(stattrak_vals) > 1:
        return False, "stattrak_mixte"
    if any(getattr(s, 'souvenir', False) for s in skins):
        return False, "souvenir_interdit"
    rarities = {getattr(s, 'rarity_id', None) for s in skins}
    if "rarity_ancient_weapon" in rarities and len(skins) != 5:
        return False, "covert_requires_5_inputs"
    return True, "valid"


def scan_all_opportunities(filters: UserFilters | None = None) -> list[dict]:
    """
    Scanne toutes les combinaisons de trade-up mono-collection (10 inputs identiques).
    """
    if filters is None:
        filters = UserFilters()

    with get_session() as session:
        # Charger tous les prix d'achat et de vente
        buy_prices = _get_platform_prices(session, filters.source_buy)
        sell_prices = _get_platform_prices(session, filters.source_sell)

        # Charger tous les skins éligibles comme inputs (avec prix d'achat)
        eligible_inputs = session.query(Skin).filter(Skin.id.in_(buy_prices.keys())).all()

        # Charger tous les pools trade-up
        all_pools = session.query(TradeupPool).all()

        # Index pool : input_skin_id → {collection_id: [output_skin_id, ...]}
        pool_idx: dict[str, dict[str, list[str]]] = {}
        for tp in all_pools:
            pool_idx.setdefault(tp.input_skin_id, {}).setdefault(
                tp.collection_id, []
            ).append(tp.output_skin_id)

        # Charger les noms des skins pour les outputs
        skin_names: dict[str, str] = {s.id: s.name for s in session.query(Skin).all()}

        opportunities = []
        checked = 0
        # Compteurs de filtres pour diagnostic
        f_no_pool = 0; f_budget = 0; f_pool_size = 0; f_no_output = 0; f_roi = 0; f_liquidity = 0; f_ev_err = 0

        for skin in eligible_inputs:
            skin_id = skin.id
            if skin_id not in pool_idx:
                f_no_pool += 1
                continue

            bp_data = buy_prices.get(skin_id, {})
            raw_buy  = bp_data.get("buy_price")
            med_buy  = bp_data.get("median_price")
            quantity = bp_data.get("quantity")

            # Détection anomalie min_price (spec §4.4 — fallback sur médiane)
            if raw_buy and med_buy and is_price_anomaly(raw_buy, med_buy):
                base_price = med_buy
            else:
                base_price = raw_buy

            # Vérification liquidité inputs + prix estimé corrigé (spec §4.5)
            liq_result = check_input_liquidity(quantity, base_price, med_buy, qty_needed=10)
            input_liquidity = liq_result["status"]
            if input_liquidity == "out_of_stock":
                continue  # inexécutable — rejet

            buy_price = liq_result["estimated_unit_price"]
            if not buy_price or buy_price <= 0:
                continue

            # Filtre liquidité input (volume journalier)
            input_vol_24h = bp_data.get("volume_24h") or 0.0
            if input_vol_24h < filters.min_volume_input:
                continue

            # Filtre quantité minimum (exécutabilité)
            if quantity is not None and quantity < filters.min_quantity_input:
                continue

            # Règle Covert post-oct 2025 : rarity_ancient_weapon → 5 inputs (spec §4.4)
            n_inputs = 5 if skin.rarity_id == "rarity_ancient_weapon" else 10

            cost_n = buy_price * n_inputs
            if cost_n > filters.max_budget:
                f_budget += 1
                continue

            # ── Recipe velocity (spec §4.7) ──
            # Détecte si les inputs sont en hausse rapide en 24h (signe de saturation)
            inp_avg_24h = bp_data.get("avg_24h")
            inp_avg_7d  = bp_data.get("avg_7d")
            if inp_avg_24h and inp_avg_7d and inp_avg_7d > 0:
                input_trend = (inp_avg_24h - inp_avg_7d) / inp_avg_7d
            else:
                input_trend = 0.0
            velocity_alert = input_trend > 0.05

            for coll_id, output_ids in pool_idx[skin_id].items():
                if len(output_ids) > filters.max_pool_size:
                    f_pool_size += 1
                    continue

                # Construire les outputs avec toutes les données historiques
                outputs_list: list[OutputSkin] = []
                for out_id in output_ids:
                    sp_data = sell_prices.get(out_id, {})
                    outputs_list.append(OutputSkin(
                        skin_id=out_id,
                        name=skin_names.get(out_id, out_id),
                        sell_price=sp_data.get("sell_price") or 0.0,
                        volume_24h=sp_data.get("volume_24h", 0.0),
                        volume_7d=sp_data.get("volume_7d", 0.0),
                        volume_30d=sp_data.get("volume_30d", 0.0),
                        median_24h=sp_data.get("median_24h"),
                        median_7d=sp_data.get("median_7d"),
                        median_30d=sp_data.get("median_30d"),
                        median_90d=sp_data.get("median_90d"),
                        avg_24h=sp_data.get("avg_24h"),
                        avg_7d=sp_data.get("avg_7d"),
                        avg_30d=sp_data.get("avg_30d"),
                        avg_90d=sp_data.get("avg_90d"),
                        source_sell=filters.source_sell,
                    ))

                if not outputs_list:
                    f_no_output += 1
                    continue

                # Construire les inputs (5 pour Covert, 10 sinon — spec §4.4)
                inputs_list = [
                    InputSkin(
                        skin_id=skin_id,
                        name=skin.name,
                        collection_id=coll_id,
                        rarity_id=skin.rarity_id,
                        buy_price=buy_price,
                        source_buy=filters.source_buy,
                    )
                    for _ in range(n_inputs)
                ]

                try:
                    result = calculate_ev(
                        inputs_list,
                        {coll_id: outputs_list},
                        source_buy=filters.source_buy,
                        source_sell=filters.source_sell,
                        min_vol_7d=filters.min_volume_sell_price,
                        exclude_trending_down=filters.exclude_trending_down,
                        input_trend=input_trend,
                        input_liquidity_status=input_liquidity,
                        vol_24h_input=input_vol_24h,
                    )
                    checked += 1
                except ValueError:
                    f_ev_err += 1
                    continue

                # Vérifier liquidité minimale après redistribution
                if result.liquidity_score * 7 < filters.min_liquidity:
                    f_liquidity += 1
                    continue

                if result.roi < filters.min_roi:
                    f_roi += 1
                    continue

                if filters.exclude_high_volatility and result.high_volatility:
                    continue

                if result.kontract_score < filters.min_kontract_score:
                    continue

                # ── Scalability (spec §4.7) ──
                # max_repeats = min(qty_i // n_inputs) pour tous les inputs
                qty_val = quantity if quantity is not None else 999
                max_repeats = qty_val // n_inputs
                bottleneck_skin = skin.name if max_repeats < 10 else None

                combo_hash = f"{skin_id}:{coll_id}"
                opportunities.append({
                    "combo_hash": combo_hash,
                    "input_skin_id": skin_id,
                    "input_name": skin.name,
                    "input_rarity_id": skin.rarity_id,
                    "collection_id": coll_id,
                    "ev_nette": result.ev_nette,
                    "roi": result.roi,
                    "cout_ajuste": result.cout_ajuste,
                    "pool_size": result.pool_size,
                    "nb_valid_outputs": result.nb_valid_outputs,
                    "pool_score": result.pool_score,
                    "liquidity_score": result.liquidity_score * 7,
                    "win_prob": result.win_prob,
                    "cv_pond": result.cv_pond,
                    "ev_ajustee": result.ev_ajustee,
                    "floor_ratio": result.floor_ratio,
                    "kontract_score": result.kontract_score,
                    "price_reliability": result.price_reliability,
                    "high_volatility": result.high_volatility,
                    "strategy_used": "pure",
                    "input_liquidity_status": input_liquidity,
                    "velocity_alert": velocity_alert,
                    "max_repeats": max_repeats,
                    "bottleneck_skin": bottleneck_skin,
                    "outputs": result.outputs,
                })

    # Tri par ROI décroissant
    opportunities.sort(key=lambda x: x["roi"], reverse=True)

    logger.info(
        "Scan terminé : %d combos évalués, %d opportunités qualifiées (ROI ≥ %.0f%%)",
        checked, len(opportunities), filters.min_roi,
    )
    logger.info(
        "Filtres : pas_pool=%d budget=%d pool_size=%d no_output=%d ev_err=%d roi=%d liquidity=%d | PASS=%d",
        f_no_pool, f_budget, f_pool_size, f_no_output, f_ev_err, f_roi, f_liquidity, len(opportunities)
    )
    return opportunities


def save_opportunities(opportunities: list[dict]) -> int:
    """Persiste les opportunités qualifiées en BDD. Retourne le nombre sauvegardé."""
    if not opportunities:
        return 0

    saved = 0
    with get_session() as session:
        for opp in opportunities:
            existing = (
                session.query(Opportunity)
                .filter_by(combo_hash=opp["combo_hash"])
                .first()
            )
            n_inp = len(json.loads(opp.get("inputs_json", "[]")) or [opp["input_skin_id"]] * 10)
            if existing:
                existing.ev_nette = opp["ev_nette"]
                existing.roi = opp["roi"]
                existing.pool_size = opp["pool_size"]
                existing.liquidity_score = opp["liquidity_score"]
                existing.price_reliability = opp["price_reliability"]
                existing.cv_pond = opp["cv_pond"]
                existing.win_prob = opp["win_prob"]
                existing.kontract_score = opp["kontract_score"]
                existing.floor_ratio = opp["floor_ratio"]
                existing.input_liquidity_status = opp["input_liquidity_status"]
                existing.cout_ajuste = opp["cout_ajuste"]
                existing.high_volatility = opp["high_volatility"]
            else:
                n_inputs_save = 5 if opp.get("input_rarity_id") == "rarity_ancient_weapon" else 10
                session.add(Opportunity(
                    combo_hash=opp["combo_hash"],
                    inputs_json=json.dumps([opp["input_skin_id"]] * n_inputs_save),
                    ev_nette=opp["ev_nette"],
                    roi=opp["roi"],
                    pool_size=opp["pool_size"],
                    liquidity_score=opp["liquidity_score"],
                    price_reliability=opp["price_reliability"],
                    cv_pond=opp["cv_pond"],
                    win_prob=opp["win_prob"],
                    kontract_score=opp["kontract_score"],
                    floor_ratio=opp["floor_ratio"],
                    input_liquidity_status=opp["input_liquidity_status"],
                    strategy_used="pure",
                    cout_ajuste=opp["cout_ajuste"],
                    high_volatility=opp["high_volatility"],
                ))
                saved += 1
        session.commit()

    return saved


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    filters = UserFilters(min_roi=5.0, max_budget=500.0, max_pool_size=10, min_liquidity=1.0)
    opps = scan_all_opportunities(filters)

    print(f"\n{len(opps)} opportunités trouvées (ROI ≥ {filters.min_roi}%)\n")
    print(f"{'Input skin':<40} {'ROI':>7} {'EV nette':>9} {'Pool':>6} {'Vol 24h':>8}")
    print("-" * 75)
    for opp in opps[:20]:
        print(
            f"{opp['input_name']:<40} "
            f"{opp['roi']:>6.1f}% "
            f"{opp['ev_nette']:>8.2f}€ "
            f"{opp['pool_size']:>6} "
            f"{opp['liquidity_score']:>8.1f}"
        )

    if opps:
        print(f"\nMeilleure opportunité :")
        best = opps[0]
        print(f"  Input  : {best['input_name']} (coût 10x = {best['cout_ajuste']:.2f}€)")
        print(f"  ROI    : {best['roi']:.1f}%")
        print(f"  EV nette : {best['ev_nette']:.2f}€")
        print(f"  Win prob : {best['win_prob']:.1f}%")
        print("  Outputs :")
        for o in best["outputs"][:5]:
            print(f"    {o['name']}: {o['prob']}% → {o['sell_price']:.2f}€")
