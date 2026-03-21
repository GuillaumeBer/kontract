"""
main.py — Kontract.gg
Orchestration principale : scheduler APScheduler + bot Telegram.

Cycles :
  - Toutes les 5 min  : fetch Skinport prices → scan EV → alertes Telegram
  - Toutes les 10 min : fetch Steam prices (skins prioritaires seulement)
  - 1x / semaine      : mise à jour BDD ByMykel (nouvelles collections)

Usage :
  python main.py
"""

import asyncio
import logging
import os
import json
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from alerts.notifier import match_opportunities_to_users
from alerts.telegram_bot import send_notifications
from data.bymykel import build_collections_db
from data.database import init_db
from engine.scanner import UserFilters, save_opportunities, scan_all_opportunities
from fetcher.skinport import update_prices_from_skinport
from fetcher.skinport_ws import SkinportSniper
from fetcher.steam import update_prices_from_steam
from engine.recommender import ActionRecommender
from engine.output_detector import OutputDetector
from engine.sell_engine import OutputSellEngine
from engine.momentum import PriceSignalEngine

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("kontract.main")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Filtres par défaut du cycle de scan
DEFAULT_FILTERS = UserFilters(
    min_roi=0.0,             # Permettre de voir toutes les opportunités neutres/positives
    max_budget=400.0,
    max_pool_size=15,        # Elargir pour inclure des collections plus grandes
    min_volume_sell_price=10.0,  # Match avec les réglages UI recommandés
    min_liquidity=0.0,       # 0 = inclure toutes les opps même sans historique de ventes
    min_volume_input=0.0,    # Pas de filtre volume input côté backend — laisser le scanner décider
)


async def job_fetch_and_scan() -> None:
    """Job toutes les 5 min : prix Skinport → scan EV → alertes."""
    logger.info("=== Cycle fetch+scan démarré ===")

    try:
        from data.database import redis_client
        if redis_client:
            redis_client.set("scan:last_start", datetime.now().isoformat())
        else:
            # Fallback fichier si Redis est absent
            with open("scan_status.json", "w") as f:
                json.dump({"last_start": datetime.now().isoformat()}, f)
            
        stats = await update_prices_from_skinport()
        logger.info("Skinport: %s", stats)
    except Exception as exc:
        logger.error("Erreur fetch Skinport: %s", exc)

    try:
        opps = scan_all_opportunities(DEFAULT_FILTERS)
        saved = save_opportunities(opps)
        logger.info("Scanner: %d opportunités, %d nouvelles sauvegardées", len(opps), saved)
    except Exception as exc:
        logger.error("Erreur scanner: %s", exc)
        opps = []

    if opps and TELEGRAM_BOT_TOKEN:
        try:
            notifications = match_opportunities_to_users(opps)
            await send_notifications(notifications, TELEGRAM_BOT_TOKEN)
            logger.info("Telegram: %d notifications envoyées", len(notifications))
        except Exception as exc:
            logger.error("Erreur Telegram: %s", exc)

    logger.info("=== Cycle terminé ===")


async def job_action_plan() -> None:
    """Job toutes les 5 min : génère le plan d'action centralisé."""
    logger.info("=== Génération du Plan d'Action ===")
    from data.database import get_session
    from data.models import TradeupBasket, Opportunity
    
    with get_session() as session:
        baskets = session.query(TradeupBasket).filter_by(status="active").all()
        # Mocking opportunities for now - in real it would come from recent scans
        opps_raw = session.query(Opportunity).order_by(Opportunity.kontract_score.desc()).limit(10).all()
        opps = [
            {"input_name": o.combo_hash.split(":")[0], "roi": o.roi, "kontract_score": o.kontract_score, "cout_ajuste": o.cout_ajuste}
            for o in opps_raw
        ]

    recommender = ActionRecommender()
    # Simple mock check for free slots (Spec §4.8)
    free_slots = 5 - len(baskets)
    
    actions = recommender.generate_action_plan(opps, baskets, [])
    
    if actions:
        logger.info("Plan d'Action : %d recommandations générées.", len(actions))
        # Top action info
        top = actions[0]
        logger.info("Top Action : [%s] %s - %s", top.type.value, top.opportunity_name, top.reason)
    
    logger.info("=== Plan d'Action terminé ===")


async def job_fetch_steam() -> None:
    """Job toutes les 10 min : prix Steam sur les skins outputs prioritaires (cross-check §2.3)."""
    logger.info("=== Fetch Steam prices démarré ===")
    try:
        # Limiter aux 50 premiers skins outputs pour rester dans le rate limit (100 req/5min)
        from data.database import get_session
        from data.models import Skin as SkinModel
        with get_session() as session:
            priority_ids = [
                s.id for s in session.query(SkinModel)
                .filter(SkinModel.market_hash_name.isnot(None))
                .limit(50)
                .all()
            ]
        stats = await update_prices_from_steam(skin_ids=priority_ids, delay=1.5)
        logger.info("Steam: %s", stats)
    except Exception as exc:
        logger.error("Erreur fetch Steam: %s", exc)


async def job_update_bymykel() -> None:
    """Job hebdomadaire : mise à jour BDD depuis ByMykel."""
    logger.info("=== MAJ ByMykel démarrée ===")
    try:
        stats = await build_collections_db()
        logger.info("ByMykel: %s", stats)
    except Exception as exc:
        logger.error("Erreur ByMykel: %s", exc)


async def startup() -> None:
    """Initialisation au démarrage."""
    logger.info("Kontract.gg démarrage...")

    init_db()
    logger.info("Base de données initialisée")

    # Vérifier si la BDD est vide → charger ByMykel
    from data.database import get_session
    from data.models import Skin
    with get_session() as session:
        skin_count = session.query(Skin).count()

    if skin_count == 0:
        logger.info("BDD vide — chargement initial ByMykel...")
        await job_update_bymykel()
    else:
        logger.info("BDD existante : %d skins chargés", skin_count)

    # Premier cycle immédiat
    await job_fetch_and_scan()


async def _sniper_telegram_broadcast(msg: str) -> None:
    """Envoie une alerte snipe à tous les utilisateurs Telegram actifs."""
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        from data.database import get_session
        from data.models import UserAlert
        with get_session() as session:
            chat_ids = [a.user_id for a in session.query(UserAlert).filter_by(active=True).all()]
        await send_notifications([(cid, msg) for cid in chat_ids], TELEGRAM_BOT_TOKEN)
    except Exception as e:
        logger.error("Erreur broadcast Telegram snipe : %s", e)


async def main() -> None:
    await startup()

    scheduler = AsyncIOScheduler()

    # Job principal toutes les 5 min
    scheduler.add_job(job_fetch_and_scan, "interval", minutes=5, id="fetch_scan")

    # Génération du plan d'action toutes les 5 min (décalé de 30s)
    scheduler.add_job(job_action_plan, "interval", minutes=5, id="action_plan", start_date=datetime.now() + timedelta(seconds=30))

    # Fetch Steam prices toutes les 10 min (cross-check §2.3, spec §3.2)
    scheduler.add_job(job_fetch_steam, "interval", minutes=10, id="steam_fetch")

    # MAJ ByMykel hebdomadaire
    scheduler.add_job(job_update_bymykel, "interval", weeks=1, id="bymykel_update")

    scheduler.start()
    logger.info("Scheduler démarré (Ctrl+C pour arrêter)")

    # Sniper REST Skinport — tâche asyncio parallèle au scheduler (poll toutes les 90s)
    sniper = SkinportSniper(
        snipe_discount=float(os.getenv("SNIPE_DISCOUNT", "0.12")),
        telegram_notify_fn=_sniper_telegram_broadcast if TELEGRAM_BOT_TOKEN else None,
    )
    asyncio.create_task(sniper.run())
    logger.info("Sniper REST démarré (seuil %.0f%%)", float(os.getenv("SNIPE_DISCOUNT", "0.12")) * 100)

    # Démarrage optionnel du bot Telegram en parallèle
    if TELEGRAM_BOT_TOKEN:
        try:
            from alerts.telegram_bot import build_application
            logger.info("Bot Telegram activé")
            app = build_application(TELEGRAM_BOT_TOKEN)
            await app.initialize()
            await app.start()
            await app.updater.start_polling()
        except Exception as exc:
            logger.warning("Bot Telegram désactivé: %s", exc)

    # Boucle principale
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Arrêt...")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
