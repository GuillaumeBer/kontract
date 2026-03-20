"""
Module bymykel.py
Télécharge les données de structure CS2 depuis ByMykel CSGO-API et peuple la BDD.
Source : https://github.com/ByMykel/CSGO-API
"""

import asyncio
import logging
import httpx
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from data.database import init_db, get_session
from data.models import Collection, Skin, TradeupPool

logger = logging.getLogger(__name__)

BASE_URL = "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en"

# Ordre de rareté croissant — trade-up : tier N → tier N+1
RARITY_ORDER = [
    "rarity_common_weapon",      # Consumer Grade (gris)
    "rarity_uncommon_weapon",    # Industrial Grade (bleu clair)
    "rarity_rare_weapon",        # Mil-Spec Grade (bleu)
    "rarity_mythical_weapon",    # Restricted (violet)
    "rarity_legendary_weapon",   # Classified (rose)
    "rarity_ancient_weapon",     # Covert (rouge)
]


def get_output_pool(collection: dict, input_rarity_id: str) -> list:
    """Retourne les skins du tier supérieur dans la collection."""
    try:
        next_tier_idx = RARITY_ORDER.index(input_rarity_id) + 1
    except ValueError:
        return []
    if next_tier_idx >= len(RARITY_ORDER):
        return []
    next_tier = RARITY_ORDER[next_tier_idx]
    return [s for s in collection["contains"] if s["rarity"]["id"] == next_tier]


async def _fetch_json(url: str) -> list | dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()


async def build_collections_db() -> dict:
    """
    Télécharge collections.json + skins.json depuis ByMykel,
    peuple les tables collections, skins et tradeup_pool.
    Retourne des stats : {collections, skins, tradeup_links}.
    """
    init_db()

    logger.info("Téléchargement collections.json...")
    collections = await _fetch_json(f"{BASE_URL}/collections.json")

    logger.info("Téléchargement skins.json...")
    skins_list = await _fetch_json(f"{BASE_URL}/skins.json")

    # Index des skins détaillés par id
    skins_idx: dict[str, dict] = {s["id"]: s for s in skins_list}

    stats = {"collections": 0, "skins": 0, "tradeup_links": 0, "tradeup_links_removed": 0}

    # Ensemble des triplets (input, output, collection) valides selon ByMykel
    valid_triplets: set[tuple[str, str, str]] = set()

    with get_session() as session:
        for collection in collections:
            # Upsert collection
            session.merge(Collection(
                id=collection["id"],
                name=collection["name"],
                release_date=collection.get("release_date"),
                active=True,
            ))
            stats["collections"] += 1

            for skin_ref in collection.get("contains", []):
                full = skins_idx.get(skin_ref["id"], {})

                # Construire market_hash_name depuis le skin détaillé
                market_hash_name = full.get("market_hash_name") or full.get("name")

                session.merge(Skin(
                    id=skin_ref["id"],
                    name=skin_ref.get("name", ""),
                    weapon=full.get("weapon", {}).get("name") if full.get("weapon") else None,
                    collection_id=collection["id"],
                    rarity_id=skin_ref["rarity"]["id"],
                    rarity_name=skin_ref["rarity"].get("name"),
                    float_min=full.get("min_float"),
                    float_max=full.get("max_float"),
                    stattrak=full.get("stattrak", False),
                    market_hash_name=market_hash_name,
                ))
                stats["skins"] += 1

                # Construction du pool d'outputs
                outputs = get_output_pool(collection, skin_ref["rarity"]["id"])
                for output in outputs:
                    valid_triplets.add((skin_ref["id"], output["id"], collection["id"]))
                    # Upsert via INSERT OR IGNORE (SQLite)
                    stmt = sqlite_insert(TradeupPool).values(
                        input_skin_id=skin_ref["id"],
                        output_skin_id=output["id"],
                        collection_id=collection["id"],
                    ).on_conflict_do_nothing()
                    session.execute(stmt)
                    stats["tradeup_links"] += 1

        # Supprimer les liens TradeupPool obsolètes (absents des données ByMykel actuelles)
        stale_pools = [
            row for row in session.query(TradeupPool).all()
            if (row.input_skin_id, row.output_skin_id, row.collection_id) not in valid_triplets
        ]
        for row in stale_pools:
            session.delete(row)
        stats["tradeup_links_removed"] = len(stale_pools)
        if stale_pools:
            logger.info("TradeupPool : %d liens obsolètes supprimés", len(stale_pools))

        # Marquer les collections absentes de ByMykel comme inactives
        current_collection_ids = {c["id"] for c in collections}
        session.query(Collection).filter(
            Collection.id.notin_(current_collection_ids)
        ).update({"active": False}, synchronize_session=False)

        session.commit()

    logger.info(
        "BDD mise à jour : %d collections, %d skins, %d liens trade-up (%d supprimés)",
        stats["collections"], stats["skins"], stats["tradeup_links"], stats["tradeup_links_removed"],
    )
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = asyncio.run(build_collections_db())
    print(f"\nRésultat : {result}")

    # Vérification rapide sur 5 collections
    print("\nVérification des pools d'outputs (5 premiers inputs avec pool non vide) :")
    with get_session() as session:
        from data.models import TradeupPool, Skin as SkinModel
        from sqlalchemy import func

        rows = (
            session.query(
                TradeupPool.input_skin_id,
                func.count(TradeupPool.output_skin_id).label("pool_size"),
            )
            .group_by(TradeupPool.input_skin_id)
            .order_by(func.count(TradeupPool.output_skin_id).desc())
            .limit(5)
            .all()
        )
        for row in rows:
            skin = session.get(SkinModel, row.input_skin_id)
            name = skin.name if skin else row.input_skin_id
            print(f"  {name} → {row.pool_size} outputs possibles")
