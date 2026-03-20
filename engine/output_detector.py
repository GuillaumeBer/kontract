import time
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class OutputDetector:
    """
    OutputDetector handles automated Steam inventory polling to identify
    trade-up results. (Spec §4.9)
    """

    def __init__(self, steam_fetcher):
        self.steam_fetcher = steam_fetcher
        self.snapshots = {} # basket_id -> list of assetids

    def take_snapshot(self, basket_id: int):
        """Take a snapshot of the current Steam inventory before trade-up."""
        inventory = self.steam_fetcher.fetch_inventory()
        self.snapshots[basket_id] = [item["assetid"] for item in inventory]
        logger.info(f"Snapshot taken for basket {basket_id}: {len(self.snapshots[basket_id])} items.")

    def poll_for_result(self, basket_id: int, max_retries: int = 5) -> dict | None:
        """
        Poll Steam inventory to find the new item (output).
        """
        if basket_id not in self.snapshots:
            logger.error(f"No snapshot found for basket {basket_id}")
            return None

        for i in range(max_retries):
            logger.info(f"Polling Steam inventory for basket {basket_id} result (attempt {i+1})...")
            new_inventory = self.steam_fetcher.fetch_inventory()
            new_assetids = [item["assetid"] for item in new_inventory]
            
            # Identify new item (assetid present in new inventory but not in snapshot)
            diff = set(new_assetids) - set(self.snapshots[basket_id])
            
            if diff:
                new_assetid = list(diff)[0]
                detected_item = next((item for item in new_inventory if item["assetid"] == new_assetid), None)
                
                if detected_item:
                    logger.info(f"Output detected! Skin: {detected_item['name']}, AssetID: {new_assetid}")
                    # In V1: Call CSFloat API to get the float_value
                    # For MVP: Return the item data
                    return {
                        "name": detected_item["name"],
                        "assetid": new_assetid,
                        "float_value": 0.0, # Placeholder
                        "detected_at": datetime.utcnow()
                    }
            
            time.sleep(15) # Wait between polls (§4.9)

        logger.warning(f"No result detected for basket {basket_id} after {max_retries} attempts.")
        return None

    def verify_float_prediction(self, basket, actual_float: float) -> dict:
        """Compare predicted float with actual float to check formula precision."""
        # This will be used in P&L reporting
        delta = abs(basket.predicted_output_float - actual_float)
        return {
            "predicted": basket.predicted_output_float,
            "actual": actual_float,
            "delta": delta,
            "precision": 1.0 - (delta / actual_float) if actual_float > 0 else 0.0
        }
