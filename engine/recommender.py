from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import uuid

class ActionType(Enum):
    BUY_NOW = "buy_now"
    BUY_WATCH = "buy_watch"
    SELL_NOW = "sell_now"
    SELL_HOLD = "sell_hold"
    EXECUTE = "execute"
    ABANDON = "abandon"

class ActionPriority(Enum):
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"

@dataclass
class Action:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: ActionType = ActionType.BUY_NOW
    priority: ActionPriority = ActionPriority.NORMAL
    market_hash_name: str = ""
    sale_id: str = None
    assetid: str = None
    platform: str = "skinport"
    price: float = 0.0
    price_target: float = None
    url: str = ""
    basket_id: int = None
    opportunity_name: str = ""
    display_name: str = ""
    quantity: int = None
    reason: str = ""
    score: float = 0.0
    float_val: float = None
    float_norm: float = None
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=2))
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "pending"  # "pending" | "executed" | "expired"

class ActionRecommender:
    """
    ActionRecommender synthesizes market signals into prioritized Action objects.
    (Spec §4.13)
    """

    def generate_action_plan(self, opportunities: list[dict], baskets: list, inventory: list) -> list[Action]:
        """
        Generates a consolidated list of recommended actions.
        """
        import re
        def slugify(text: str) -> str:
            # Skinport slug: lowercase, alphanum only, replaced by '-'
            text = text.lower()
            text = text.replace("™", "").replace("★", "")
            text = re.sub(r'[^a-z0-9]+', '-', text)
            return text.strip('-')

        actions = []

        # 1. Check for EXECUTE actions (Baskets 10/10)
        for basket in baskets:
            if basket.status == "active" and len(basket.items) >= 10:
                actions.append(Action(
                    type=ActionType.EXECUTE,
                    priority=ActionPriority.URGENT,
                    opportunity_name=basket.opportunity_name,
                    basket_id=basket.id,
                    reason=f"Panier complet ({len(basket.items)}/10). Prêt pour exécution.",
                    score=100.0
                ))

        # 2. Check for BUY_NOW actions (Urgent opportunities)
        for opp in opportunities[:3]:
            name = opp["input_name"]
            # Priorité : URL officielle de l'API > slug généré
            url = opp.get("item_page") or f"https://skinport.com/item/{slugify(name)}"
            
            actions.append(Action(
                type=ActionType.BUY_NOW,
                priority=ActionPriority.HIGH,
                market_hash_name=name,
                display_name=opp.get("display_name", name),
                quantity=opp.get("quantity"),
                price=opp["cout_ajuste"] / 10,
                url=url,
                opportunity_name=opp.get("display_name", name),
                reason=f"Top opportunité (ROI {opp['roi']:.1f}%). Kontract Score {opp['kontract_score']:.1f}.",
                score=opp["kontract_score"]
            ))

        # 3. Check for ABANDON actions (Spec §4.7.1)
        # (Simplified: if ROI dropped below 1% for an active basket)
        for basket in baskets:
            if basket.status == "active" and basket.current_roi < 1.0:
                actions.append(Action(
                    type=ActionType.ABANDON,
                    priority=ActionPriority.NORMAL,
                    opportunity_name=basket.opportunity_name,
                    basket_id=basket.id,
                    reason="ROI insuffisant (< 1%). Abandon recommandé.",
                    score=0.0
                ))

        # Sort by priority and score
        priority_map = {ActionPriority.URGENT: 0, ActionPriority.HIGH: 1, ActionPriority.NORMAL: 2, ActionPriority.LOW: 3}
        actions.sort(key=lambda x: (priority_map[x.priority], -x.score))

        return actions
