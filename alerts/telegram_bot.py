"""
Module alerts/telegram_bot.py
Bot Telegram pour les alertes Kontract.gg.

Commandes disponibles :
  /start         — inscription + affichage du profil par défaut
  /profil        — afficher les paramètres actuels
  /config        — configurer les filtres (ex: /config roi=15 pool=3 budget=200)
  /pause         — désactiver les alertes
  /resume        — réactiver les alertes
  /scan          — lancer un scan immédiat et afficher les 5 meilleures opps

Usage :
  export TELEGRAM_BOT_TOKEN=your_token
  python -m alerts.telegram_bot
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from data.database import get_session, init_db
from data.models import UserAlert
from engine.scanner import UserFilters, scan_all_opportunities

load_dotenv()
logger = logging.getLogger(__name__)


def _get_or_create_alert(session, chat_id: str) -> UserAlert:
    alert = session.query(UserAlert).filter_by(user_id=chat_id).first()
    if not alert:
        alert = UserAlert(
            user_id=chat_id,
            min_roi=10.0,
            max_budget=100.0,
            max_pool_size=5,
            min_liquidity=3.0,
            source_buy="skinport",
            source_sell="skinport",
            active=True,
        )
        session.add(alert)
        session.commit()
    return alert


def _format_profile(alert: UserAlert) -> str:
    status = "✅ Active" if alert.active else "⏸ En pause"
    trending = "Oui" if getattr(alert, "exclude_trending_down", False) else "Non"
    volatility = "Oui" if getattr(alert, "exclude_high_volatility", False) else "Non"
    ks_min = getattr(alert, "min_kontract_score", 0.0) or 0.0
    min_qty = getattr(alert, "min_input_qty", 10) or 10
    return (
        f"*Votre profil Kontract.gg*\n\n"
        f"Statut : {status}\n"
        f"ROI minimum : {alert.min_roi}%\n"
        f"Budget max (10x inputs) : {alert.max_budget}€\n"
        f"Pool max (nb outcomes) : {alert.max_pool_size}\n"
        f"Liquidité min (ventes/j) : {alert.min_liquidity}\n"
        f"Kontract Score min : {ks_min}\n"
        f"Quantité input min : {min_qty}\n"
        f"Exclure tendances baissières : {trending}\n"
        f"Exclure haute volatilité : {volatility}\n"
        f"Source achat : {alert.source_buy}\n"
        f"Source vente : {alert.source_sell}\n\n"
        f"_Pour modifier : /config roi=15 pool=3 budget=200 liquidity=5 ks=0.2 qty=10 trending=1 volatility=1_"
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    with get_session() as session:
        alert = _get_or_create_alert(session, chat_id)
        profile = _format_profile(alert)

    await update.message.reply_markdown(
        f"Bienvenue sur *Kontract.gg* 🎯\n\n"
        f"Je vous alerterai dès qu'un trade-up profitable est détecté.\n\n"
        f"{profile}"
    )


async def cmd_profil(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    with get_session() as session:
        alert = _get_or_create_alert(session, chat_id)
        profile = _format_profile(alert)
    await update.message.reply_markdown(profile)


async def cmd_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage : /config roi=15 pool=3 budget=200 liquidity=5 ks=0.2 qty=10 trending=1 volatility=1
    Paramètres acceptés : roi, pool, budget, liquidity, ks, qty, trending, volatility, source_buy, source_sell
    """
    chat_id = str(update.effective_chat.id)
    args = context.args or []

    if not args:
        await update.message.reply_text(
            "Usage : /config roi=15 pool=3 budget=200 liquidity=5 ks=0.2 qty=10 trending=1 volatility=1\n"
            "Paramètres : roi, pool, budget, liquidity, ks (Kontract Score min), qty (quantité input min), "
            "trending (0/1), volatility (0/1)"
        )
        return

    params = {}
    for arg in args:
        if "=" in arg:
            key, val = arg.split("=", 1)
            params[key.lower()] = val

    updated = []
    with get_session() as session:
        alert = _get_or_create_alert(session, chat_id)

        if "roi" in params:
            try:
                alert.min_roi = float(params["roi"])
                updated.append(f"ROI min → {alert.min_roi}%")
            except ValueError:
                pass
        if "pool" in params:
            try:
                alert.max_pool_size = int(params["pool"])
                updated.append(f"Pool max → {alert.max_pool_size}")
            except ValueError:
                pass
        if "budget" in params:
            try:
                alert.max_budget = float(params["budget"])
                updated.append(f"Budget max → {alert.max_budget}€")
            except ValueError:
                pass
        if "liquidity" in params:
            try:
                alert.min_liquidity = float(params["liquidity"])
                updated.append(f"Liquidité min → {alert.min_liquidity} ventes/j")
            except ValueError:
                pass
        if "ks" in params:
            try:
                alert.min_kontract_score = float(params["ks"])
                updated.append(f"Kontract Score min → {alert.min_kontract_score}")
            except ValueError:
                pass
        if "qty" in params:
            try:
                alert.min_input_qty = int(params["qty"])
                updated.append(f"Quantité input min → {alert.min_input_qty}")
            except ValueError:
                pass
        if "trending" in params:
            alert.exclude_trending_down = params["trending"] not in ("0", "false", "non")
            updated.append(f"Exclure tendances baissières → {'Oui' if alert.exclude_trending_down else 'Non'}")
        if "volatility" in params:
            alert.exclude_high_volatility = params["volatility"] not in ("0", "false", "non")
            updated.append(f"Exclure haute volatilité → {'Oui' if alert.exclude_high_volatility else 'Non'}")

        session.commit()

    if updated:
        msg = "✅ Profil mis à jour :\n" + "\n".join(f"  • {u}" for u in updated)
    else:
        msg = "❌ Aucun paramètre valide. Usage : /config roi=15 pool=3 budget=200"

    await update.message.reply_text(msg)


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    with get_session() as session:
        alert = _get_or_create_alert(session, chat_id)
        alert.active = False
        session.commit()
    await update.message.reply_text("⏸ Alertes désactivées. Utilisez /resume pour les réactiver.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    with get_session() as session:
        alert = _get_or_create_alert(session, chat_id)
        alert.active = True
        session.commit()
    await update.message.reply_text("✅ Alertes réactivées !")


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lance un scan immédiat et affiche les 5 meilleures opportunités."""
    chat_id = str(update.effective_chat.id)

    await update.message.reply_text("🔍 Scan en cours...")

    with get_session() as session:
        alert = _get_or_create_alert(session, chat_id)
        filters = UserFilters(
            min_roi=alert.min_roi,
            max_budget=alert.max_budget,
            max_pool_size=alert.max_pool_size,
            min_liquidity=alert.min_liquidity,
            source_buy=alert.source_buy,
            source_sell=alert.source_sell,
        )

    opps = scan_all_opportunities(filters)

    if not opps:
        await update.message.reply_text(
            "Aucune opportunité trouvée avec vos filtres actuels.\n"
            "Essayez /config roi=5 pool=10 liquidity=0"
        )
        return

    header = f"*{len(opps)} opportunités trouvées* (top 5) :\n\n"
    lines = []
    for opp in opps[:5]:
        lines.append(
            f"*{opp['input_name']}*\n"
            f"  ROI: {opp['roi']:.1f}% | EV: {opp['ev_nette']:.2f}€ | Pool: {opp['pool_size']}"
        )

    await update.message.reply_markdown(header + "\n\n".join(lines))


async def send_notifications(notifications: list[tuple[str, str]], token: str) -> None:
    """Envoie les messages Telegram pour les opportunités matchées."""
    if not notifications or not token:
        return

    app = Application.builder().token(token).build()
    async with app:
        for chat_id, message in notifications:
            try:
                await app.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="Markdown",
                )
            except Exception as exc:
                logger.warning("Échec envoi Telegram à %s : %s", chat_id, exc)


def build_application(token: str) -> Application:
    """Construit et configure l'application Telegram."""
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("profil", cmd_profil))
    app.add_handler(CommandHandler("config", cmd_config))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("scan", cmd_scan))
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("⚠️  TELEGRAM_BOT_TOKEN non configuré dans .env")
        print("Test local : création d'un utilisateur fictif en BDD")
        init_db()
        with get_session() as session:
            alert = UserAlert(
                user_id="test_user_123",
                min_roi=10.0,
                max_budget=100.0,
                max_pool_size=5,
                min_liquidity=0.0,
                active=True,
            )
            session.merge(alert)
            session.commit()
        print("✅ Utilisateur test créé : user_id=test_user_123")
        print("Configurez TELEGRAM_BOT_TOKEN dans .env pour démarrer le bot")
    else:
        init_db()
        app = build_application(token)
        print("🤖 Bot Telegram démarré... (Ctrl+C pour arrêter)")
        app.run_polling()
