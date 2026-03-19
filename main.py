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

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from alerts.notifier import match_opportunities_to_users
from alerts.telegram_bot import send_notifications
from data.bymykel import build_collections_db
from data.database import init_db
from engine.scanner import UserFilters, save_opportunities, scan_all_opportunities
from fetcher.skinport import update_prices_from_skinport

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
    min_roi=10.0,
    max_budget=200.0,
    max_pool_size=5,
    min_liquidity=0.0,  # 0 jusqu'à ce que les volumes soient correctement chargés
)


async def job_fetch_and_scan() -> None:
    """Job toutes les 5 min : prix Skinport → scan EV → alertes."""
    logger.info("=== Cycle fetch+scan démarré ===")

    try:
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


async def job_update_bymykel() -> None:
    """Job hebdomadaire : mise à jour BDD depuis ByMykel."""
    logger.info("=== MAJ ByMykel démarrée ===")
    try:
        stats = build_collections_db()
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


async def main() -> None:
    await startup()

    scheduler = AsyncIOScheduler()

    # Job principal toutes les 5 min
    scheduler.add_job(job_fetch_and_scan, "interval", minutes=5, id="fetch_scan")

    # MAJ ByMykel hebdomadaire
    scheduler.add_job(job_update_bymykel, "interval", weeks=1, id="bymykel_update")

    scheduler.start()
    logger.info("Scheduler démarré (Ctrl+C pour arrêter)")

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
