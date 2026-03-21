"""
Module fetcher/skinport_ws.py
Sniper temps réel via l'API REST publique Skinport.

Stratégie : poll /v1/items toutes les POLL_INTERVAL secondes.
Chaque item expose min_price (= prix du listing le moins cher disponible).
Si min_price ≤ median_ref × (1 - snipe_discount) et que le skin est
un input d'une opportunité connue → alerte snipe.

Déduplication : une alerte par (market_hash_name, prix_déclenché).
Re-alerte si le prix descend encore de plus de 2%, ou si le listing
disparaît puis réapparaît.

Pourquoi pas WebSocket ?
  Le feed Socket.IO de Skinport est protégé par Cloudflare (HTTP 403
  sans cookies de session navigateur réels). L'API REST publique
  (api.skinport.com/v1/items) est accessible sans authentification
  et retourne min_price en temps quasi-réel (~3-4 min de fraîcheur).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Awaitable

import httpx

from data.database import get_session
from data.models import Opportunity, Price, Skin, SnipeAlert

logger = logging.getLogger(__name__)

SKINPORT_API_URL = "https://api.skinport.com/v1/items"
SKINPORT_APPID = 730
SKINPORT_CURRENCY = "EUR"

DEFAULT_SNIPE_DISCOUNT = 0.12   # seuil par défaut : -12 % vs médiane
POLL_INTERVAL = 90              # secondes entre deux polls (données refresh ~3-4min)
REFRESH_INTERVAL = 300          # rafraîchissement watch list (secondes)
RETRIGGER_DROP = 0.02           # re-alerter si prix redescend encore de 2 %
RATE_LIMIT_FALLBACK_WAIT = 120  # secondes à attendre si 429 sans Retry-After


# ---------------------------------------------------------------------------
# Formatage message Telegram
# ---------------------------------------------------------------------------

def format_snipe_message(entry: dict, listing_price: float, discount_pct: float,
                          roi_sniped: float, item_url: str) -> str:
    ks = entry["opp_kontract_score"]
    ks_emoji = "🟢" if ks >= 0.5 else "🟡" if ks >= 0.2 else "🟠"
    return (
        f"🎯 *SNIPE DÉTECTÉ !*\n\n"
        f"*Skin* : {entry['skin_name']}\n"
        f"*Prix listé* : {listing_price:.2f}€\n"
        f"*Médiane* : {entry['median_price']:.2f}€\n"
        f"*Remise* : `-{discount_pct:.1f}%`\n"
        f"*ROI base → boosté* : {entry['opp_roi']:.1f}% → *{roi_sniped:.1f}%*\n"
        f"*Kontract Score* : {ks_emoji} {ks:.2f}\n"
        f"[→ Acheter sur Skinport]({item_url})"
    )


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------

class SkinportSniper:
    """
    Sniper REST-polling sur l'API Skinport.

    Usage dans main.py :
        sniper = SkinportSniper(snipe_discount=0.12, telegram_notify_fn=...)
        asyncio.create_task(sniper.run())
    """

    def __init__(
        self,
        snipe_discount: float = DEFAULT_SNIPE_DISCOUNT,
        telegram_notify_fn: Callable[[str], Awaitable] | None = None,
    ):
        self.snipe_discount = snipe_discount
        self.telegram_notify_fn = telegram_notify_fn
        self._watch_list: dict[str, dict] = {}
        # Déduplication : mhn → dernier prix qui a déclenché une alerte
        self._last_snipe: dict[str, float] = {}
        # Cache ETag pour requêtes conditionnelles (évite de retraiter des données inchangées)
        self._etag: str | None = None
        self._http = httpx.AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
            },
            timeout=20,
            follow_redirects=True,
        )

    # -----------------------------------------------------------------------
    # Watch list (index BDD → mémoire)
    # -----------------------------------------------------------------------

    async def refresh_watch_list(self) -> None:
        """
        Recharge depuis la BDD la liste des skins à surveiller.
        Index : market_hash_name → {skin_id, median_price, opp_data, ...}
        """
        watch: dict[str, dict] = {}

        with get_session() as session:
            opps = session.query(Opportunity).all()

            for opp in opps:
                skin_id = opp.combo_hash.split(":")[0]

                price_row = session.query(Price).filter_by(
                    skin_id=skin_id, platform="skinport"
                ).first()
                if not price_row or not price_row.buy_price:
                    continue

                skin_row = session.query(Skin).filter_by(id=skin_id).first()
                if not skin_row or not skin_row.market_hash_name:
                    continue

                # Médiane de référence : 7j > 30j > sell_price > buy_price
                median = (
                    price_row.median_7d
                    or price_row.median_30d
                    or price_row.sell_price
                    or price_row.buy_price
                )
                if not median:
                    continue

                n_inputs = 5 if skin_row.rarity_id == "rarity_ancient_weapon" else 10
                cout_ajuste = opp.cout_ajuste or (price_row.buy_price * n_inputs)

                watch[skin_row.market_hash_name] = {
                    "skin_id": skin_id,
                    "skin_name": skin_row.name,
                    "market_hash_name": skin_row.market_hash_name,
                    "median_price": median,
                    "buy_price": price_row.buy_price,
                    "opp_combo_hash": opp.combo_hash,
                    "opp_roi": opp.roi or 0.0,
                    "opp_ev_nette": opp.ev_nette or 0.0,
                    "opp_cout_ajuste": cout_ajuste,
                    "opp_kontract_score": opp.kontract_score or 0.0,
                    "n_inputs": n_inputs,
                    "item_page": price_row.item_page or "",
                }

        self._watch_list = watch
        logger.info("Watch list sniper rafraîchie : %d skins surveillés", len(watch))

    # -----------------------------------------------------------------------
    # Poll REST
    # -----------------------------------------------------------------------

    async def _fetch_listings(self) -> dict[str, float] | None:
        """
        Appelle GET /v1/items et retourne {market_hash_name: min_price}.
        min_price = prix du listing le moins cher disponible sur Skinport.

        Retourne None si les données n'ont pas changé depuis le dernier poll (304).
        Lève httpx.HTTPStatusError(429) si rate-limited.
        """
        headers = {}
        if self._etag:
            headers["If-None-Match"] = self._etag

        resp = await self._http.get(
            SKINPORT_API_URL,
            params={"app_id": SKINPORT_APPID, "currency": SKINPORT_CURRENCY},
            headers=headers,
        )

        if resp.status_code == 304:
            logger.debug("Poll Skinport : données inchangées (304 Not Modified)")
            return None  # rien à retraiter

        resp.raise_for_status()  # lève HTTPStatusError pour 429, 5xx, etc.

        if etag := resp.headers.get("etag"):
            self._etag = etag

        data = resp.json()
        return {
            item["market_hash_name"]: item["min_price"]
            for item in data
            if item.get("min_price") and item.get("min_price") > 0
        }

    async def _process_listings(self, listings: dict[str, float]) -> None:
        """
        Compare les prix courants à la watch list et déclenche les snipes.
        """
        # Nettoyer les entrées expirées (listing disparu → reset dédup)
        to_remove = [
            mhn for mhn in list(self._last_snipe)
            if mhn not in listings
               or listings[mhn] > self._watch_list.get(mhn, {}).get("median_price", 0)
               * (1.0 - self.snipe_discount) * 1.05
        ]
        for mhn in to_remove:
            del self._last_snipe[mhn]

        for mhn, min_price in listings.items():
            if mhn not in self._watch_list:
                continue

            entry = self._watch_list[mhn]
            median = entry["median_price"]
            threshold = median * (1.0 - self.snipe_discount)

            if min_price > threshold:
                continue  # pas suffisamment sous le marché

            # Déduplication : ne re-alerter que si le prix baisse encore
            prev = self._last_snipe.get(mhn)
            if prev is not None and min_price >= prev * (1.0 - RETRIGGER_DROP):
                continue  # même listing déjà signalé, pas assez de drop supplémentaire

            discount_pct = (median - min_price) / median * 100.0

            # ROI boosté : 1 input acheté au prix snipé, le reste au médian
            savings = median - min_price
            new_cout = max(entry["opp_cout_ajuste"] - savings, 0.01)
            new_ev_nette = entry["opp_ev_nette"] + savings
            roi_sniped = (new_ev_nette / new_cout) * 100.0

            item_url = entry["item_page"] or f"https://skinport.com/market?item={mhn}"

            logger.info(
                "🎯 SNIPE : %s @ %.2f€ (médiane %.2f€, -%.1f%%) | ROI %.1f%% → %.1f%%",
                mhn, min_price, median, discount_pct,
                entry["opp_roi"], roi_sniped,
            )

            self._last_snipe[mhn] = min_price

            await self._save_snipe(entry, min_price, discount_pct, roi_sniped, item_url)

            if self.telegram_notify_fn:
                msg = format_snipe_message(entry, min_price, discount_pct,
                                           roi_sniped, item_url)
                try:
                    await self.telegram_notify_fn(msg)
                except Exception as e:
                    logger.error("Erreur notification Telegram snipe : %s", e)

    async def _save_snipe(self, entry: dict, listing_price: float, discount_pct: float,
                           roi_sniped: float, item_url: str) -> None:
        try:
            with get_session() as session:
                session.add(SnipeAlert(
                    skin_id=entry["skin_id"],
                    market_hash_name=entry["market_hash_name"],
                    listing_price=round(listing_price, 4),
                    median_price=round(entry["median_price"], 4),
                    discount_pct=round(discount_pct, 2),
                    opp_combo_hash=entry["opp_combo_hash"],
                    opp_roi_base=round(entry["opp_roi"], 2),
                    opp_roi_sniped=round(roi_sniped, 2),
                    opp_kontract_score=round(entry["opp_kontract_score"], 4),
                    sale_id=None,
                    item_url=item_url,
                    detected_at=datetime.now(timezone.utc),
                    status="active",
                ))
                session.commit()
        except Exception as e:
            logger.error("Erreur sauvegarde SnipeAlert : %s", e)

    # -----------------------------------------------------------------------
    # Boucle principale
    # -----------------------------------------------------------------------

    async def run(self) -> None:
        """
        Lance le sniper : polling REST toutes les POLL_INTERVAL secondes.
        Refresh de la watch list toutes les REFRESH_INTERVAL secondes.
        """
        await self.refresh_watch_list()
        last_refresh = asyncio.get_event_loop().time()

        consecutive_errors = 0
        logger.info(
            "Sniper REST Skinport démarré (poll toutes les %ds, seuil -%.0f%%)",
            POLL_INTERVAL, self.snipe_discount * 100,
        )

        while True:
            wait = POLL_INTERVAL
            try:
                # Rafraîchir la watch list si besoin
                now = asyncio.get_event_loop().time()
                if now - last_refresh >= REFRESH_INTERVAL:
                    await self.refresh_watch_list()
                    last_refresh = now

                listings = await self._fetch_listings()
                if listings is not None:
                    logger.debug("Poll Skinport : %d items reçus", len(listings))
                    await self._process_listings(listings)
                consecutive_errors = 0

            except httpx.HTTPStatusError as e:
                consecutive_errors += 1
                status = e.response.status_code
                if status == 429:
                    # Rate-limited : respecter Retry-After ou attente par défaut
                    retry_after = e.response.headers.get("retry-after")
                    wait = int(retry_after) if retry_after and retry_after.isdigit() else RATE_LIMIT_FALLBACK_WAIT
                    logger.warning(
                        "API Skinport : rate limit (429). Pause de %ds avant prochain poll.", wait
                    )
                else:
                    wait = min(POLL_INTERVAL * (2 ** min(consecutive_errors - 1, 4)), 600)
                    logger.warning("API Skinport HTTP %s — retry dans %ds", status, wait)

            except httpx.RequestError as e:
                consecutive_errors += 1
                wait = min(POLL_INTERVAL * (2 ** min(consecutive_errors - 1, 4)), 600)
                logger.warning("API Skinport réseau : %s — retry dans %ds", e, wait)

            except Exception as e:
                consecutive_errors += 1
                wait = min(POLL_INTERVAL * (2 ** min(consecutive_errors - 1, 4)), 600)
                logger.error("Sniper erreur inattendue : %s — retry dans %ds", e, wait)

            await asyncio.sleep(wait)
