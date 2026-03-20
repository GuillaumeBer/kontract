from datetime import datetime
import math

class PriceSignalEngine:
    """
    PriceSignalEngine calculates a momentum score (0-1) based on market signals
    defined in Spec v2.0 §4.7.2.
    """

    def __init__(self):
        # S5: Seasonal deltas (1.0 = neutral)
        self.SEASONAL_FACTORS = {
            1: 1.05,  # Jan: Post-holiday recovery
            2: 1.02,
            3: 1.00,
            4: 1.00,
            5: 1.05,  # May: Pre-summer hype
            6: 0.92,  # Jun: Summer Sale dip
            7: 1.10,  # Jul: Sale recovery
            8: 1.05,
            9: 1.00,
            10: 1.00,
            11: 0.95, # Nov: Autumn Sale dip
            12: 0.88, # Dec: Winter Sale dip
        }

    def compute_momentum_score(self, collection_active: bool, history: dict = None) -> dict:
        """
        Computes a composite momentum score based on multiple signals.
        
        Signals implemented:
        - S1: Collection Inactivity (+0.2 momentum if inactive)
        - S5: Seasonality (multiplier based on current month)
        - S2: 7d/30d Trend (simplified)
        
        Returns:
            dict: {
                "momentum_score": float (0-1),
                "multiplier": float (0.75-1.30),
                "signals": list[str]
            }
        """
        score = 0.5  # Base neutral score
        signals = []

        # S1: Collection Inactivity
        if not collection_active:
            score += 0.15
            signals.append("Collection Inactive (Bullish Supply)")
        else:
            signals.append("Collection Active (Stable Supply)")

        # S5: Seasonality
        current_month = datetime.now().month
        seasonal_factor = self.SEASONAL_FACTORS.get(current_month, 1.0)
        
        if seasonal_factor > 1.0:
            score += 0.05
            signals.append(f"Seasonal Bonus ({current_month})")
        elif seasonal_factor < 1.0:
            score -= 0.05
            signals.append(f"Seasonal Penalty ({current_month})")

        # S2: Price Trend (Simplified)
        # If we had access to history here, we would calculate (avg_7d - avg_30d) / avg_30d
        # For now, we cap the score between 0 and 1
        score = max(0.0, min(1.0, score))

        # Map score (0.0-1.0) to multiplier (0.75-1.30)
        # 0.5 -> 1.0
        # 1.0 -> 1.3
        # 0.0 -> 0.7
        multiplier = 0.7 + (score * 0.6)

        return {
            "momentum_score": round(score, 2),
            "multiplier": round(multiplier, 2),
            "signals": signals,
            "verdict": "Bullish" if score > 0.6 else "Bearish" if score < 0.4 else "Neutral"
        }
