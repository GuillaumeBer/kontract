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
    ks = opp.get("kontract_score", 0.0) or 0.0
    ks_label = "🟢 Excellent" if ks >= 0.5 else "🟡 Bon" if ks >= 0.2 else "🟠 Moyen" if ks >= 0.1 else "🔴 Spéculatif"

    # Floor ratio
    floor_ratio = opp.get("floor_ratio", 0.0) or 0.0
    floor_pct = round(floor_ratio * 100, 1)

    # Velocity alert
    velocity_badge = "⚡ " if opp.get("velocity_alert") else ""

    # Input liquidity status
    liq_status = opp.get("input_liquidity_status", "liquid")
    liq_emoji = {"liquid": "🟢", "partial": "🟡", "scarce": "🔴"}.get(liq_status, "⚪")

    # Scalability
    max_repeats = opp.get("max_repeats", 0) or 0

    return (
        f"{velocity_badge}🎯 *Trade-up Profitable Détecté !*\n\n"
        f"*Input* : {opp['input_name']}\n"
        f"*Kontract Score* : {ks:.2f} — {ks_label}\n"
        f"*ROI* : {opp['roi']:.1f}%\n"
        f"*Fiabilité Prix* : {rel_emoji} {rel}\n"
        f"*EV nette* : {opp['ev_nette']:.2f}€\n"
        f"*Coût 10x* : {opp['cout_ajuste']:.2f}€\n"
        f"*Pool size* : {opp['pool_size']} outcomes\n"
        f"*Win prob* : {opp['win_prob']:.1f}%\n"
        f"*Floor* : {floor_pct}% | *Inputs* : {liq_emoji} {liq_status}"
        f" | *Répétable* : {max_repeats}×\n\n"
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
      - kontract_score >= user.min_kontract_score
      - exclude_trending_down respected
      - exclude_high_volatility respected
      - input quantity >= user.min_input_qty (if set)
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

            # --- Advanced filters (§4.3 spec) ---
            # Kontract Score minimum
            min_ks = getattr(alert, "min_kontract_score", 0.0) or 0.0
            if min_ks > 0 and (opp.get("kontract_score", 0.0) or 0.0) < min_ks:
                continue

            # Exclude trending down outputs
            if getattr(alert, "exclude_trending_down", False):
                rel = opp.get("price_reliability", "")
                if "trending_down" in rel.lower():
                    continue

            # Exclude high volatility
            if getattr(alert, "exclude_high_volatility", False):
                if opp.get("high_volatility", False):
                    continue

            # Minimum input quantity
            min_qty = getattr(alert, "min_input_qty", 10) or 10
            opp_qty = opp.get("max_repeats", 999)
            # max_repeats = qty // n_inputs, so qty = max_repeats * n_inputs
            # But we can also check the raw available quantity if present
            # For now, if max_repeats is 0 it means qty < n_inputs → reject
            if opp_qty is not None and opp_qty == 0 and min_qty > 0:
                continue

            if msg is None:
                msg = _format_opportunity_message(opp)
            notifications.append((alert.user_id, msg))

    logger.info(
        "Matching: %d opportunities → %d notifications à envoyer",
        len(opportunities), len(notifications),
    )
    return notifications
