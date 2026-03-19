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
    max_budget: float = 100.0
    max_pool_size: int = 5
    min_liquidity: float = 3.0
    source_buy: str = "skinport"
    source_sell: str = "skinport"


def _get_platform_prices(session, platform: str) -> dict[str, dict]:
    """Retourne un dict skin_id → {buy_price, sell_price, volume_24h}."""
    rows = session.query(Price).filter_by(platform=platform).all()
    return {
        r.skin_id: {
            "buy_price": r.buy_price,
            "sell_price": r.sell_price,
            "volume_24h": r.volume_24h or 0.0,
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


def scan_all_opportunities(filters: UserFilters | None = None) -> list[dict]:
    """
    Scanne toutes les combinaisons de trade-up mono-collection (10 inputs identiques).

    Stratégie MVP simplifiée :
      - Pour chaque skin avec prix d'achat, calcule le trade-up de 10 inputs identiques
      - Identifie les outputs possibles (tradeup_pool)
      - Calcule l'EV et filtre selon les critères utilisateur

    Retourne une liste de dicts avec les métriques de chaque opportunité qualifiée.
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

        for skin in eligible_inputs:
            skin_id = skin.id
            if skin_id not in pool_idx:
                continue

            bp_data = buy_prices.get(skin_id, {})
            buy_price = bp_data.get("buy_price")
            if not buy_price or buy_price <= 0:
                continue

            cost_10 = buy_price * 10
            if cost_10 > filters.max_budget:
                continue

            for coll_id, output_ids in pool_idx[skin_id].items():
                if len(output_ids) > filters.max_pool_size:
                    continue

                # Construire les outputs avec leurs prix de vente
                outputs_list: list[OutputSkin] = []
                for out_id in output_ids:
                    sp_data = sell_prices.get(out_id, {})
                    sp = sp_data.get("sell_price") or sp_data.get("buy_price")
                    if sp and sp > 0:
                        outputs_list.append(OutputSkin(
                            skin_id=out_id,
                            name=skin_names.get(out_id, out_id),
                            sell_price=sp,
                            volume_24h=sp_data.get("volume_24h", 0.0),
                            source_sell=filters.source_sell,
                        ))

                if not outputs_list:
                    continue

                # Vérifier liquidité minimale
                max_vol = max(o.volume_24h for o in outputs_list)
                if max_vol < filters.min_liquidity:
                    continue

                # Construire les 10 inputs identiques
                inputs_list = [
                    InputSkin(
                        skin_id=skin_id,
                        name=skin.name,
                        collection_id=coll_id,
                        rarity_id=skin.rarity_id,
                        buy_price=buy_price,
                        source_buy=filters.source_buy,
                    )
                    for _ in range(10)
                ]

                try:
                    result = calculate_ev(
                        inputs_list,
                        {coll_id: outputs_list},
                        source_buy=filters.source_buy,
                        source_sell=filters.source_sell,
                    )
                    checked += 1
                except ValueError:
                    continue

                if result.roi < filters.min_roi:
                    continue

                combo_hash = f"{skin_id}:{coll_id}"
                opportunities.append({
                    "combo_hash": combo_hash,
                    "input_skin_id": skin_id,
                    "input_name": skin.name,
                    "collection_id": coll_id,
                    "ev_nette": result.ev_nette,
                    "roi": result.roi,
                    "cout_ajuste": result.cout_ajuste,
                    "pool_size": result.pool_size,
                    "pool_score": result.pool_score,
                    "liquidity_score": result.liquidity_score,
                    "win_prob": result.win_prob,
                    "jackpot_ratio": result.jackpot_ratio,
                    "ev_ajustee": result.ev_ajustee,
                    "kontract_score": result.kontract_score,
                    "outputs": result.outputs,
                })

    # Tri par ROI décroissant
    opportunities.sort(key=lambda x: x["roi"], reverse=True)

    logger.info(
        "Scan terminé : %d combos évalués, %d opportunités qualifiées (ROI ≥ %.0f%%)",
        checked, len(opportunities), filters.min_roi,
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
            if existing:
                existing.ev_nette = opp["ev_nette"]
                existing.roi = opp["roi"]
                existing.pool_size = opp["pool_size"]
                existing.liquidity_score = opp["liquidity_score"]
            else:
                session.add(Opportunity(
                    combo_hash=opp["combo_hash"],
                    inputs_json=json.dumps([opp["input_skin_id"]] * 10),
                    ev_nette=opp["ev_nette"],
                    roi=opp["roi"],
                    pool_size=opp["pool_size"],
                    liquidity_score=opp["liquidity_score"],
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
