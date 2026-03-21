"""
Module fetcher/skinport_ws.py
Sniper temps réel via le feed Socket.IO public de Skinport.

Surveille les nouveaux listings CS2 et déclenche une alerte immédiate
quand un skin est listé en dessous de (median × (1 - snipe_discount))
ET que ce skin est un input d'une opportunité trade-up connue.

Architecture :
  - Connexion persistante Socket.IO v4 à wss://skinport.com
  - Index en mémoire (watch_list) chargé depuis BDD : market_hash_name → opp data
  - Rafraîchissement de l'index toutes les REFRESH_INTERVAL secondes
  - Calcul du ROI boosté : (ev_nette + savings) / (cout_ajuste - savings) × 100
  - Sauvegarde en BDD (SnipeAlert) + notification Telegram optionnelle

Format du feed Skinport saleFeed :
  {"appid": 730, "sales": [{"id": 123, "market_hash_name": "...",
                             "salePrice": 1234, "currency": "EUR",
                             "url": "/item/csgo/..."}]}
  salePrice est en centimes (1234 = 12.34 EUR).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Awaitable

import socketio

from data.database import get_session
from data.models import Opportunity, Price, Skin, SnipeAlert

logger = logging.getLogger(__name__)

SKINPORT_WS_URL = "wss://skinport.com"
SKINPORT_APPID = 730
SKINPORT_CURRENCY = "EUR"
DEFAULT_SNIPE_DISCOUNT = 0.12   # seuil par défaut : -12% vs médiane
REFRESH_INTERVAL = 300          # rafraîchissement watch list (secondes)


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
    Connecteur Socket.IO Skinport avec détection de snipes en temps réel.

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
        self._sio = socketio.AsyncClient(
            reconnection=True,
            reconnection_attempts=0,   # infini
            reconnection_delay=5,
            reconnection_delay_max=60,
            logger=False,
            engineio_logger=False,
        )
        self._register_handlers()

    def _register_handlers(self) -> None:
        sio = self._sio

        @sio.event
        async def connect():
            logger.info("Skinport WS connecté — souscription au feed CS2 (appid=%d)", SKINPORT_APPID)
            await sio.emit("saleFeedSubscribe", {
                "appid": SKINPORT_APPID,
                "currency": SKINPORT_CURRENCY,
            })

        @sio.event
        async def disconnect():
            logger.warning("Skinport WS déconnecté — reconnexion automatique en cours...")

        @sio.event
        async def connect_error(data):
            logger.error("Skinport WS erreur de connexion : %s", data)

        @sio.on("saleFeed")
        async def on_sale_feed(data):
            await self._process_sale_feed(data)

    # -----------------------------------------------------------------------
    # Watch list
    # -----------------------------------------------------------------------

    async def refresh_watch_list(self) -> None:
        """
        Recharge depuis la BDD la liste des skins à surveiller.
        index : market_hash_name → {skin_id, median_price, opp_data, ...}
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
    # Traitement du feed
    # -----------------------------------------------------------------------

    async def _process_sale_feed(self, data: dict) -> None:
        sales = data.get("sales", [])
        for sale in sales:
            mhn = sale.get("market_hash_name", "")
            if mhn not in self._watch_list:
                continue

            # salePrice est en centimes sur Skinport (ex: 1234 = 12.34€)
            raw_price = sale.get("salePrice", 0)
            listing_price = raw_price / 100.0
            if listing_price <= 0:
                continue

            entry = self._watch_list[mhn]
            median = entry["median_price"]
            threshold = median * (1.0 - self.snipe_discount)

            if listing_price > threshold:
                continue  # pas suffisamment sous le marché

            discount_pct = (median - listing_price) / median * 100.0

            # ROI boosté : 1 input acheté au prix snipé, le reste au médian
            # ev_nette reste identique (dépend des outputs), coût diminue
            savings = median - listing_price
            new_cout = max(entry["opp_cout_ajuste"] - savings, 0.01)
            new_ev_nette = entry["opp_ev_nette"] + savings
            roi_sniped = (new_ev_nette / new_cout) * 100.0

            sale_id = str(sale.get("id", ""))
            raw_url = sale.get("url", "")
            item_url = (
                f"https://skinport.com{raw_url}" if raw_url
                else entry["item_page"]
            )

            logger.info(
                "🎯 SNIPE : %s @ %.2f€ (médiane %.2f€, -%.1f%%) | ROI %.1f%% → %.1f%%",
                mhn, listing_price, median, discount_pct,
                entry["opp_roi"], roi_sniped,
            )

            await self._save_snipe(entry, listing_price, discount_pct,
                                   roi_sniped, sale_id, item_url)

            if self.telegram_notify_fn:
                msg = format_snipe_message(entry, listing_price, discount_pct,
                                           roi_sniped, item_url)
                try:
                    await self.telegram_notify_fn(msg)
                except Exception as e:
                    logger.error("Erreur notification Telegram snipe : %s", e)

    async def _save_snipe(self, entry: dict, listing_price: float, discount_pct: float,
                           roi_sniped: float, sale_id: str, item_url: str) -> None:
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
                    sale_id=sale_id,
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
        Lance le sniper : connexion WS persistante + refresh périodique de l'index.
        Gère la reconnexion automatique en cas de coupure.
        """
        await self.refresh_watch_list()

        async def _refresh_loop() -> None:
            while True:
                await asyncio.sleep(REFRESH_INTERVAL)
                await self.refresh_watch_list()

        asyncio.create_task(_refresh_loop())

        while True:
            try:
                logger.info("Connexion au feed Skinport WebSocket...")
                await self._sio.connect(
                    SKINPORT_WS_URL,
                    transports=["websocket"],
                    socketio_path="/socket.io/",
                )
                await self._sio.wait()
            except Exception as e:
                logger.error("Skinport WS erreur inattendue : %s — retry dans 15s", e)
                await asyncio.sleep(15)
