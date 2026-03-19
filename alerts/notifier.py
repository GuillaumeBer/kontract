"""
Module alerts/notifier.py
Match les opportunités détectées avec les profils d'alerte utilisateurs.

Pour chaque opportunité qualifiée, envoie une notification Telegram
à tous les utilisateurs dont les filtres correspondent.
"""

import logging

from data.database import get_session
from data.models import UserAlert

logger = logging.getLogger(__name__)


def _format_opportunity_message(opp: dict) -> str:
    """Formate un message Telegram Markdown pour une opportunité."""
    outputs_text = "\n".join(
        f"  • {o['name']}: {o['prob']:.1f}% → {o['sell_price']:.2f}€ ({o.get('reliability', 'low')})"
        for o in opp.get("outputs", [])[:5]
    )
    rel = opp.get("price_reliability", "low").upper()
    rel_emoji = "🟢" if rel == "HIGH" else "🟡" if rel == "MEDIUM" else "🔴"
    
    return (
        f"🎯 *Trade-up Profitable Détecté !*\n\n"
        f"*Input* : {opp['input_name']}\n"
        f"*ROI* : {opp['roi']:.1f}%\n"
        f"*Fiabilité Prix* : {rel_emoji} {rel}\n"
        f"*EV nette* : {opp['ev_nette']:.2f}€\n"
        f"*Coût 10x* : {opp['cout_ajuste']:.2f}€\n"
        f"*Pool size* : {opp['pool_size']} outcomes\n"
        f"*Win prob* : {opp['win_prob']:.1f}%\n\n"
        f"*Outputs possibles* :\n{outputs_text}"
    )


def match_opportunities_to_users(opportunities: list[dict]) -> list[tuple[str, str]]:
    """
    Pour chaque opportunité, retourne les (chat_id, message) à envoyer.

    Une opportunité correspond à un utilisateur si :
      - roi >= user.min_roi
      - cout_ajuste <= user.max_budget
      - pool_size <= user.max_pool_size
      - liquidity_score >= user.min_liquidity (si > 0)
      - user.active == True
    """
    if not opportunities:
        return []

    with get_session() as session:
        active_alerts = session.query(UserAlert).filter_by(active=True).all()

    if not active_alerts:
        return []

    notifications: list[tuple[str, str]] = []

    for opp in opportunities:
        msg = None
        for alert in active_alerts:
            if opp["roi"] < alert.min_roi:
                continue
            if opp["cout_ajuste"] > alert.max_budget:
                continue
            if opp["pool_size"] > alert.max_pool_size:
                continue
            if alert.min_liquidity > 0 and opp["liquidity_score"] < alert.min_liquidity:
                continue

            if msg is None:
                msg = _format_opportunity_message(opp)
            notifications.append((alert.user_id, msg))

    logger.info(
        "Matching: %d opportunities → %d notifications à envoyer",
        len(opportunities), len(notifications),
    )
    return notifications
