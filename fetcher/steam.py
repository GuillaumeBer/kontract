"""
Module fetcher/steam.py
Client Steam Market API — prix de référence.

Rate limit : 100 req / 5 min (100 000 req/jour).
Stratégie MVP : poll toutes les 10 min, uniquement les skins outputs prioritaires.
"""

import asyncio
import logging
import urllib.parse
from datetime import datetime, timezone

import httpx
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from data.database import get_session
from data.models import Price, Skin
from data.throttler import Throttler

logger = logging.getLogger(__name__)

STEAM_API_URL = "https://steamcommunity.com/market/priceoverview/"


async def fetch_steam_price(market_hash_name: str, currency: int = 3) -> dict | None:
    """
    Récupère le prix Steam pour un skin.
    currency=3 = EUR

    Retourne dict avec lowest_price, median_price, volume ou None si erreur.
    """
    if Throttler.is_rate_limited("steam"):
        logger.warning("Steam: skipping price fetch due to active rate limit.")
        return None

    params = {
        "appid": 730,
        "currency": currency,
        "market_hash_name": market_hash_name,
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(STEAM_API_URL, params=params, timeout=15)
            if resp.status_code == 429:
                Throttler.mark_rate_limited("steam")
                return None
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                return None
            return data
        except Exception as exc:
            logger.warning("Steam fetch failed for %s: %s", market_hash_name, exc)
            return None


def _parse_steam_price(price_str: str | None) -> float | None:
    """Convertit '1,23€' ou '$1.23' en float."""
    if not price_str:
        return None
    cleaned = price_str.replace(",", ".").replace("€", "").replace("$", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


async def update_prices_from_steam(skin_ids: list[str] | None = None, delay: float = 3.0) -> dict:
    """
    Met à jour les prix Steam pour les skins indiqués (ou tous si None).
    `delay` (secondes) entre chaque requête pour respecter le rate limit.
    Retourne des stats : {updated, skipped, errors}.
    """
    stats = {"updated": 0, "skipped": 0, "errors": 0}

    with get_session() as session:
        query = session.query(Skin).filter(Skin.market_hash_name.isnot(None))
        if skin_ids:
            query = query.filter(Skin.id.in_(skin_ids))
        skins = query.all()

    for skin in skins:
        data = await fetch_steam_price(skin.market_hash_name)
        if not data:
            stats["errors"] += 1
            await asyncio.sleep(delay)
            continue

        lowest = _parse_steam_price(data.get("lowest_price"))
        median = _parse_steam_price(data.get("median_price"))
        volume_str = data.get("volume", "0").replace(",", "")
        try:
            volume = float(volume_str)
        except ValueError:
            volume = None

        with get_session() as session:
            stmt = sqlite_insert(Price).values(
                skin_id=skin.id,
                platform="steam",
                buy_price=lowest,
                sell_price=median,
                volume_24h=volume,
                volume_7d=None,
                updated_at=datetime.now(timezone.utc),
            ).on_conflict_do_update(
                index_elements=["skin_id", "platform"],
                set_=dict(
                    buy_price=lowest,
                    sell_price=median,
                    volume_24h=volume,
                    updated_at=datetime.now(timezone.utc),
                ),
            )
            session.execute(stmt)
            session.commit()

        stats["updated"] += 1
        await asyncio.sleep(delay)

    logger.info("Steam prices updated: %s", stats)
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    async def _test():
        # Tester sur 3 skins connus
        test_skins = [
            "AK-47 | Redline (Field-Tested)",
            "AWP | Asiimov (Field-Tested)",
            "M4A4 | Howl (Field-Tested)",
        ]
        print("Test fetch_steam_price sur 3 skins :")
        for name in test_skins:
            data = await fetch_steam_price(name)
            if data:
                print(f"  {name}: lowest={data.get('lowest_price')}, median={data.get('median_price')}, vol={data.get('volume')}")
            else:
                print(f"  {name}: non disponible")
            await asyncio.sleep(2)

    asyncio.run(_test())
