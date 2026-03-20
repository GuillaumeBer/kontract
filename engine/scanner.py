"""
Module engine/scanner.py
Scan vectorisé NumPy de toutes les combinaisons de trade-up valides.

Le scanner identifie les trade-ups avec EV positive en parcourant :
  - Tous les skins avec prix d'achat disponible
  - Tous les outputs possibles depuis tradeup_pool
  - Filtres configurables par utilisateur (ROI, budget, pool, liquidité)
  - Deux stratégies : pure (10 même collection) et fillers (7+3 collection mixte)
"""

import json
import logging
from dataclasses import dataclass

import numpy as np

from data.database import get_session
from data.models import Opportunity, Price, Skin, TradeupPool, Collection
from engine.ev_calculator import InputSkin, OutputSkin, calculate_ev

logger = logging.getLogger(__name__)


@dataclass
class UserFilters:
    min_roi: float = 10.0
    max_budget: float = 200.0              # spec §4.3 : défaut 200 €
    max_pool_size: int = 5
    min_liquidity: float = 1.0              # spec §4.5 : défaut 1.0
    min_volume_sell_price: int = 10         # ventes min pour fiabilité statistique (plage 10–100)
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


def _build_filler_index(
    eligible_skins: list,
    buy_prices: dict[str, dict],
    pool_idx: dict[str, dict[str, list[str]]],
) -> dict[str, list[tuple]]:
    """
    Build an index: rarity_id → [(skin_id, collection_id, buy_price, quantity)] sorted by price.
    Used to find the cheapest skins of a given rarity from OTHER collections for filler strategy.
    """
    rarity_skins: dict[str, list[tuple]] = {}
    for skin in eligible_skins:
        bp_data = buy_prices.get(skin.id, {})
        price = bp_data.get("buy_price")
        if not price or price <= 0:
            continue
        qty = bp_data.get("quantity")
        # Only include skins that have outputs (are valid trade-up inputs)
        if skin.id not in pool_idx:
            continue
        entry = (skin.id, skin.collection_id, price, qty, skin.name)
        rarity_skins.setdefault(skin.rarity_id, []).append(entry)

    # Sort each rarity by price ascending
    for rarity in rarity_skins:
        rarity_skins[rarity].sort(key=lambda x: x[2])

    return rarity_skins


def _get_cheapest_fillers(
    filler_index: dict[str, list[tuple]],
    rarity_id: str,
    exclude_collection_id: str,
    n: int = 3,
) -> list[tuple]:
    """
    Get the n cheapest skins of the given rarity from collections OTHER than exclude_collection_id.
    Returns list of (skin_id, collection_id, buy_price, quantity, name).
    """
    candidates = filler_index.get(rarity_id, [])
    fillers = []
    for entry in candidates:
        if entry[1] != exclude_collection_id:
            fillers.append(entry)
            if len(fillers) >= n:
                break
    return fillers


def _build_outputs_by_collection(
    output_ids_by_coll: dict[str, list[str]],
    sell_prices: dict[str, dict],
    skin_names: dict[str, str],
    source_sell: str,
) -> dict[str, list[OutputSkin]]:
    """Build OutputSkin lists grouped by collection_id."""
    result = {}
    for coll_id, out_ids in output_ids_by_coll.items():
        outputs = []
        for out_id in out_ids:
            sp_data = sell_prices.get(out_id, {})
            outputs.append(OutputSkin(
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
                source_sell=source_sell,
            ))
        if outputs:
            result[coll_id] = outputs
    return result


def _try_evaluate(
    inputs_list: list[InputSkin],
    outputs_by_coll: dict[str, list[OutputSkin]],
    filters: UserFilters,
    input_trend: float,
    input_liquidity: str,
    input_vol_24h: float,
    collection_active: bool = True,
) -> "EVResult | None":
    """Try to evaluate a trade-up, return EVResult or None if error/filtered."""
    try:
        return calculate_ev(
            inputs_list,
            outputs_by_coll,
            source_buy=filters.source_buy,
            source_sell=filters.source_sell,
            min_vol_7d=filters.min_volume_sell_price,
            exclude_trending_down=filters.exclude_trending_down,
            exclude_high_volatility=filters.exclude_high_volatility,
            input_trend=input_trend,
            input_liquidity_status=input_liquidity,
            vol_24h_input=input_vol_24h,
            collection_active=collection_active,
        )
    except ValueError:
        return None


def scan_all_opportunities(filters: UserFilters | None = None) -> list[dict]:
    """
    Scanne toutes les combinaisons de trade-up : pure (10 même collection) + fillers (7+3).
    Pour chaque input, compare les deux stratégies et garde la meilleure ROI.
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
        skin_rarities: dict[str, str] = {s.id: s.rarity_id for s in session.query(Skin).all()}
        skin_colls: dict[str, str] = {s.id: s.collection_id for s in session.query(Skin).all()}
        coll_active: dict[str, bool] = {c.id: c.active for c in session.query(Collection).all()}

        # Build filler index for strategy B (spec §4.4)
        filler_index = _build_filler_index(eligible_inputs, buy_prices, pool_idx)

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

            # Filtre quantité minimum (exécutabilité) — exclure les items en rupture
            if quantity is not None and quantity < 1:
                continue

            # Règle Covert post-oct 2025 : rarity_ancient_weapon → 5 inputs (spec §4.4)
            n_inputs = 5 if skin.rarity_id == "rarity_ancient_weapon" else 10

            cost_n = buy_price * n_inputs
            if cost_n > filters.max_budget:
                f_budget += 1
                continue

            # ── Recipe velocity (spec §4.7) ──
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

                # Build outputs for the target collection
                outputs_by_coll = _build_outputs_by_collection(
                    {coll_id: output_ids}, sell_prices, skin_names, filters.source_sell,
                )
                if not outputs_by_coll:
                    f_no_output += 1
                    continue

                # ══════════════════════════════════════════════════════
                # STRATEGY A — Pure collection (10 inputs same collection)
                # ══════════════════════════════════════════════════════
                pure_inputs = [
                    InputSkin(skin_id, skin.name, coll_id, skin.rarity_id,
                              buy_price, filters.source_buy)
                    for _ in range(n_inputs)
                ]
                result_pure = _try_evaluate(
                    pure_inputs, outputs_by_coll, filters,
                    input_trend, input_liquidity, input_vol_24h,
                    collection_active=coll_active.get(coll_id, True)
                )
                if result_pure:
                    checked += 1

                # ══════════════════════════════════════════════════════
                # STRATEGY B — Fillers (7 target + 3 cheap from other collections)
                # Only for non-Covert (10 inputs) — spec §4.4
                # ══════════════════════════════════════════════════════
                result_filler = None
                filler_info = None
                if n_inputs == 10:
                    fillers = _get_cheapest_fillers(
                        filler_index, skin.rarity_id, coll_id, n=3
                    )
                    if len(fillers) >= 3:
                        # Build the mixed outputs_by_collection (target + filler collections)
                        filler_colls = set()
                        filler_inputs = []
                        mixed_outputs_by_coll = dict(outputs_by_coll)  # start with target coll

                        for f_skin_id, f_coll_id, f_price, f_qty, f_name in fillers:
                            filler_colls.add(f_coll_id)
                            filler_inputs.append(
                                InputSkin(f_skin_id, f_name, f_coll_id, skin.rarity_id,
                                          f_price, filters.source_buy)
                            )

                        # Add filler collection outputs to the output map
                        for f_coll_id in filler_colls:
                            if f_coll_id not in mixed_outputs_by_coll:
                                # Find output IDs for this filler in its collection
                                # We need outputs of the NEXT tier in the filler's collection
                                filler_out_ids = []
                                for f_entry in fillers:
                                    if f_entry[1] == f_coll_id:
                                        f_sid = f_entry[0]
                                        if f_sid in pool_idx and f_coll_id in pool_idx[f_sid]:
                                            filler_out_ids.extend(pool_idx[f_sid][f_coll_id])
                                filler_out_ids = list(set(filler_out_ids))
                                if filler_out_ids:
                                    filler_outs = _build_outputs_by_collection(
                                        {f_coll_id: filler_out_ids},
                                        sell_prices, skin_names, filters.source_sell,
                                    )
                                    mixed_outputs_by_coll.update(filler_outs)

                        # Build 7 target + 3 filler inputs
                        mixed_inputs = [
                            InputSkin(skin_id, skin.name, coll_id, skin.rarity_id,
                                      buy_price, filters.source_buy)
                            for _ in range(7)
                        ] + filler_inputs

                        # Check total cost
                        filler_cost = sum(f[2] for f in fillers)
                        total_mixed_cost = buy_price * 7 + filler_cost
                        if total_mixed_cost <= filters.max_budget:
                            result_filler = _try_evaluate(
                                mixed_inputs, mixed_outputs_by_coll, filters,
                                input_trend, input_liquidity, input_vol_24h,
                                collection_active=coll_active.get(coll_id, True)
                            )
                            if result_filler:
                                checked += 1
                                filler_info = {
                                    "filler_skins": [f[4] for f in fillers],
                                    "filler_cost": filler_cost,
                                }

                # ══════════════════════════════════════════════════════
                # Pick the best strategy by ROI
                # ══════════════════════════════════════════════════════
                best_result = None
                strategy_used = "pure"

                if result_pure and result_filler:
                    if result_filler.roi > result_pure.roi:
                        best_result = result_filler
                        strategy_used = "fillers"
                    else:
                        best_result = result_pure
                        strategy_used = "pure"
                elif result_pure:
                    best_result = result_pure
                    strategy_used = "pure"
                elif result_filler:
                    best_result = result_filler
                    strategy_used = "fillers"
                else:
                    f_ev_err += 1
                    continue

                result = best_result

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
                qty_val = quantity if quantity is not None else 999
                max_repeats = qty_val // n_inputs
                bottleneck_skin = skin.name if max_repeats < 10 else None

                combo_hash = f"{skin_id}:{coll_id}"
                opp_dict = {
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
                    "pump_score": result.pump_score,
                    "momentum_score": result.momentum_score,
                    "momentum_multiplier": result.momentum_multiplier,
                    "kelly_criterion": result.kelly_criterion,
                    "strategy_used": strategy_used,
                    "input_liquidity_status": input_liquidity,
                    "velocity_alert": velocity_alert,
                    "max_repeats": max_repeats,
                    "bottleneck_skin": bottleneck_skin,
                    "outputs": result.outputs,
                }
                if filler_info and strategy_used == "fillers":
                    opp_dict["filler_skins"] = filler_info["filler_skins"]
                    opp_dict["filler_cost"] = filler_info["filler_cost"]
                opportunities.append(opp_dict)

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
    """Persiste les opportunités qualifiées en BDD. Retourne le nombre sauvegardé.
    Supprime les opportunités obsolètes qui ne sont plus détectées."""

    saved = 0
    with get_session() as session:
        if not opportunities:
            return 0

        # Nettoyage : supprimer les opportunités qui ne sont plus dans le scan actuel
        # (uniquement quand le scan a trouvé des résultats — évite de vider la DB en cas de rate limit ou 0 opps)
        current_hashes = {opp["combo_hash"] for opp in opportunities}
        stale = session.query(Opportunity).filter(~Opportunity.combo_hash.in_(current_hashes)).all()
        for s in stale:
            session.delete(s)
        if stale:
            session.commit()
            logger.info("Nettoyage: %d opportunités obsolètes supprimées", len(stale))

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
                existing.strategy_used = opp["strategy_used"]
                existing.cout_ajuste = opp["cout_ajuste"]
                existing.high_volatility = opp["high_volatility"]
                existing.pump_score = opp.get("pump_score", 0.0)
                existing.momentum_score = opp.get("momentum_score", 0.5)
                existing.momentum_multiplier = opp.get("momentum_multiplier", 1.0)
                existing.kelly_criterion = opp.get("kelly_criterion", 0.0)
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
                    strategy_used=opp["strategy_used"],
                    cout_ajuste=opp["cout_ajuste"],
                    high_volatility=opp["high_volatility"],
                    pump_score=opp.get("pump_score", 0.0),
                    momentum_score=opp.get("momentum_score", 0.5),
                    momentum_multiplier=opp.get("momentum_multiplier", 1.0),
                    kelly_criterion=opp.get("kelly_criterion", 0.0),
                ))
                saved += 1
        session.commit()

    return saved


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    filters = UserFilters(min_roi=5.0, max_budget=500.0, max_pool_size=10, min_liquidity=1.0)
    opps = scan_all_opportunities(filters)

    print(f"\n{len(opps)} opportunités trouvées (ROI ≥ {filters.min_roi}%)\n")
    print(f"{'Input skin':<40} {'ROI':>7} {'EV nette':>9} {'Pool':>6} {'Strat':>8}")
    print("-" * 75)
    for opp in opps[:20]:
        print(
            f"{opp['input_name']:<40} "
            f"{opp['roi']:>6.1f}% "
            f"{opp['ev_nette']:>8.2f}€ "
            f"{opp['pool_size']:>6} "
            f"{opp['strategy_used']:>8}"
        )

    if opps:
        print(f"\nMeilleure opportunité :")
        best = opps[0]
        print(f"  Input  : {best['input_name']} (coût = {best['cout_ajuste']:.2f}€)")
        print(f"  ROI    : {best['roi']:.1f}%")
        print(f"  EV nette : {best['ev_nette']:.2f}€")
        print(f"  Win prob : {best['win_prob']:.1f}%")
        print(f"  Strategy : {best['strategy_used']}")
        print("  Outputs :")
        for o in best["outputs"][:5]:
            print(f"    {o['name']}: {o['prob']}% → {o['sell_price']:.2f}€")
