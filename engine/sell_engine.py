import logging

logger = logging.getLogger(__name__)

class OutputSellEngine:
    """
    OutputSellEngine handles Hold vs Sell decisions based on momentum,
    opportunity cost (slots), and risk. (Spec §4.11)
    """

    def __init__(self, momentum_engine):
        self.momentum_engine = momentum_engine
        self.SELL_FEE = 0.03 # Skinport fee
        self.MIN_HOLD_ROI = 0.10 # Gain minimal attendu pour un hold

    def decide_hold_or_sell(self, output: dict, free_slots: int) -> dict:
        """
        Decision logic for trade-up output.
        Returns: {
            "decision": "sell" | "hold",
            "reason": str,
            "stop_loss": float,
            "expected_gain": float
        }
        """
        momentum = output.get("momentum_score", 0.5)
        price = output.get("sell_price", 0.0)
        
        # Rule 1: Sell if no free slots (opportunity cost too high)
        if free_slots == 0:
            return {
                "decision": "sell",
                "reason": "Vente immédiate — aucun slot libre pour un nouveau panier.",
                "stop_loss": None,
                "expected_gain": 0.0
            }

        # Rule 2: Hold if momentum is high
        if momentum >= 0.70:
            expected_gain = 0.15 # +15% expected
            return {
                "decision": "hold",
                "reason": f"Hold recommandé — Momentum haussier fort ({momentum}).",
                "stop_loss": price * 0.95, # Stop-loss à -5% du spot
                "expected_gain": expected_gain
            }

        # Rule 3: Sell if momentum is low or neutral
        if momentum < 0.60:
            return {
                "decision": "sell",
                "reason": f"Vente recommandée — Momentum neutre ou faible ({momentum}).",
                "stop_loss": None,
                "expected_gain": 0.0
            }

        # Default: Sell
        return {
            "decision": "sell",
            "reason": "Vente par défaut.",
            "stop_loss": None,
            "expected_gain": 0.0
        }

    def monitor_hold(self, output_id: str, current_price: float, stop_loss: float) -> str:
        """Monitor a hold position and trigger sell if stop-loss is hit."""
        if current_price <= stop_loss:
            logger.warning(f"Stop-loss HIT for output {output_id}! Sell immediately.")
            return "sell_now"
        return "continue_hold"
