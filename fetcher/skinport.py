"""
Module fetcher/skinport.py
Client async Skinport API — prix et historique de ventes.

Rate limit : 8 req / 5 min par endpoint.
Stratégie MVP : 1 appel /v1/items + 1 appel /v1/sales/history toutes les 5 min = 25% du quota.

IMPORTANT : le header Accept-Encoding: br est OBLIGATOIRE pour les deux endpoints.
"""

import logging
import json
import asyncio
from datetime import datetime, timezone

import httpx
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from data.database import get_session, redis_client
from data.models import Price, Skin
from data.throttler import Throttler

logger = logging.getLogger(__name__)

BASE_URL = "https://api.skinport.com/v1"
BROTLI_HEADERS = {"Accept-Encoding": "br"}


async def fetch_items(currency: str = "EUR") -> list[dict]:
    """
    Récupère prix min/max/moyen/médian + quantité disponible pour tous les skins.
    Retourne une liste de dicts bruts Skinport.
    """
    if Throttler.is_rate_limited("skinport"):
        logger.warning("Skinport: skipping items fetch due to active rate limit.")
        return []

    if redis_client:
        cached = redis_client.get("skinport:items")
        if cached:
            logger.info("Using cached Skinport items")
            return json.loads(cached)

    # Persist un gap de 40s min (§3.5)
    Throttler.wait_for_service("skinport:items", 40)

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/items",
                params={"app_id": 730, "currency": currency, "tradable": 1},
                headers=BROTLI_HEADERS,
                timeout=30,
            )
            if resp.status_code == 429:
                Throttler.mark_rate_limited("skinport")
                return []
            resp.raise_for_status()
            data = resp.json()
            
            if redis_client and data:
                redis_client.setex("skinport:items", 240, json.dumps(data))
            
            return data
        except Exception as e:
            logger.error(f"Skinport items fetch error: {e}")
            return []


async def fetch_sales_history(currency: str = "EUR") -> list[dict]:
    """
    Récupère les volumes de ventes sur 24h / 7j / 30j / 90j.
    Utilisé pour le score de liquidité.
    """
    if Throttler.is_rate_limited("skinport"):
        logger.warning("Skinport: skipping history fetch due to active rate limit.")
        return []

    if redis_client:
        cached = redis_client.get("skinport:history")
        if cached:
            logger.info("Using cached Skinport history")
            return json.loads(cached)

    # Persist un gap de 40s min (§3.5)
    Throttler.wait_for_service("skinport:history", 40)

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/sales/history",
                params={"app_id": 730, "currency": currency},
                headers=BROTLI_HEADERS,
                timeout=30,
            )
            if resp.status_code == 429:
                Throttler.mark_rate_limited("skinport")
                return []
            resp.raise_for_status()
            data = resp.json()

            if redis_client and data:
                redis_client.setex("skinport:history", 240, json.dumps(data))

            return data
        except Exception as e:
            logger.error(f"Skinport history fetch error: {e}")
            return []


WEAR_CONDITIONS = [
    "Field-Tested",
    "Minimal Wear",
    "Factory New",
    "Well-Worn",
    "Battle-Scarred",
]


def _build_price_index(items: list[dict]) -> dict[str, dict]:
    """Indexe les items Skinport par market_hash_name."""
    return {item["market_hash_name"]: item for item in items}


def _build_history_index(history: list[dict]) -> dict[str, dict]:
    """Indexe l'historique Skinport par market_hash_name."""
    return {item["market_hash_name"]: item for item in history}


def _find_best_skinport_match(base_name: str, price_idx: dict) -> dict | None:
    """
    Cherche le meilleur match Skinport pour un skin sans condition d'usure.
    Priorité : Field-Tested > Minimal Wear > Factory New > Well-Worn > Battle-Scarred.
    Retourne le premier match trouvé, ou None.
    """
    for wear in WEAR_CONDITIONS:
        key = f"{base_name} ({wear})"
        if key in price_idx:
            return price_idx[key]
    # Dernier recours : match exact (skins sans condition, ex: couteaux vanilla)
    return price_idx.get(base_name)


async def update_prices_from_skinport(threshold: float = 0.005) -> dict:
    """
    Fetch Skinport items + history, normalise et écrit en BDD.
    N'écrit que si la variation de prix dépasse `threshold` (0.5% par défaut).
    Met également en cache Redis (TTL 300s) si disponible.
    Retourne des stats : {updated, skipped, not_found}.
    """
    logger.info("Fetch Skinport items...")
    items = await fetch_items()
    logger.info("Fetch Skinport sales history...")
    history = await fetch_sales_history()

    price_idx = _build_price_index(items)
    history_idx = _build_history_index(history)

    stats = {"updated": 0, "skipped": 0, "not_found": 0}

    with get_session() as session:
        skins = session.query(Skin).filter(Skin.market_hash_name.isnot(None)).all()

        for skin in skins:
            sp_item = _find_best_skinport_match(skin.market_hash_name or skin.name, price_idx)
            if not sp_item:
                stats["not_found"] += 1
                continue

            sp_hist_item = _find_best_skinport_match(
                skin.market_hash_name or skin.name, history_idx
            ) or {}
            last_24h = sp_hist_item.get("last_24_hours", {}) or {}

            new_buy = sp_item.get("min_price")
            new_sell = sp_item.get("suggested_price") or sp_item.get("median_price")
            
            # Extract historical data
            last_24h = sp_hist_item.get("last_24_hours", {}) or {}
            last_7d = sp_hist_item.get("last_7_days", {}) or {}
            last_30d = sp_hist_item.get("last_30_days", {}) or {}
            last_90d = sp_hist_item.get("last_90_days", {}) or {}

            quantity   = sp_item.get("quantity")  # units disponibles
            volume_24h = last_24h.get("volume")
            volume_7d  = last_7d.get("volume")
            volume_30d = last_30d.get("volume")
            median_24h = last_24h.get("median")
            median_7d  = last_7d.get("median")
            median_30d = last_30d.get("median")
            median_90d = last_90d.get("median")
            avg_24h    = last_24h.get("avg")
            avg_7d    = last_7d.get("avg")
            avg_30d   = last_30d.get("avg")
            avg_90d   = last_90d.get("avg")

            # Vérifier variation vs prix en cache
            existing = session.query(Price).filter_by(
                skin_id=skin.id, platform="skinport"
            ).first()

            if existing and existing.sell_price and new_sell:
                # Force update if columns are still NULL (new columns migration)
                if existing.median_7d is None or existing.median_90d is None or existing.market_hash_name is None or existing.item_page is None:
                    pass 
                else:
                    variation = abs(new_sell - existing.sell_price) / existing.sell_price
                    if variation < threshold:
                        stats["skipped"] += 1
                        continue

            stmt = sqlite_insert(Price).values(
                skin_id=skin.id,
                platform="skinport",
                market_hash_name=sp_item.get("market_hash_name"),
                item_page=sp_item.get("item_page"),
                buy_price=new_buy,
                sell_price=new_sell,
                volume_24h=volume_24h,
                volume_7d=volume_7d,
                volume_30d=volume_30d,
                quantity=quantity,
                median_24h=median_24h,
                median_7d=median_7d,
                median_30d=median_30d,
                median_90d=median_90d,
                avg_24h=avg_24h,
                avg_7d=avg_7d,
                avg_30d=avg_30d,
                avg_90d=avg_90d,
                updated_at=datetime.now(timezone.utc),
            ).on_conflict_do_update(
                index_elements=["skin_id", "platform"],
                set_=dict(
                    market_hash_name=sp_item.get("market_hash_name"),
                    item_page=sp_item.get("item_page"),
                    buy_price=new_buy,
                    sell_price=new_sell,
                    volume_24h=volume_24h,
                    volume_7d=volume_7d,
                    volume_30d=volume_30d,
                    quantity=quantity,
                    median_24h=median_24h,
                    median_7d=median_7d,
                    median_30d=median_30d,
                    median_90d=median_90d,
                    avg_24h=avg_24h,
                    avg_7d=avg_7d,
                    avg_30d=avg_30d,
                    avg_90d=avg_90d,
                    updated_at=datetime.now(timezone.utc),
                ),
            )
            session.execute(stmt)
            stats["updated"] += 1

            # Cache Redis optionnel
            if redis_client:
                redis_client.setex(
                    f"price:skinport:{skin.id}",
                    300,
                    f"{new_buy},{new_sell},{volume_24h}",
                )

        session.commit()

    logger.info("Skinport prices updated: %s", stats)
    return stats


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    async def _test():
        print("Test fetch_items (5 premiers skins)...")
        items = await fetch_items()
        for item in items[:5]:
            print(f"  {item['market_hash_name']}: min={item.get('min_price')} EUR")

        print("\nTest fetch_sales_history (5 premiers skins avec volume 24h)...")
        history = await fetch_sales_history()
        shown = 0
        for item in history:
            vol = (item.get("last_24_hours") or {}).get("volume")
            if vol and shown < 5:
                print(f"  {item['market_hash_name']}: volume_24h={vol}")
                shown += 1

        print("\nMise à jour BDD...")
        stats = await update_prices_from_skinport()
        print(f"Résultat : {stats}")

    asyncio.run(_test())
