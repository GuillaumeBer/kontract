import json
import os
import time
import logging
from datetime import datetime
from data.database import redis_client

logger = logging.getLogger(__name__)

STATUS_FILE = "scan_status.json"

class Throttler:
    """
    Gère les délais entre les appels API de manière persistante (§3.5).
    Supporte Redis ou un fichier local.
    """

    @staticmethod
    def _get_ts(key: str) -> float:
        """Récupère le timestamp du dernier appel pour une clé."""
        if redis_client:
            try:
                val = redis_client.get(f"throttle:{key}")
                return float(val) if val else 0.0
            except Exception:
                pass
        
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, "r") as f:
                    data = json.load(f)
                    return data.get(f"throttle_{key}", 0.0)
            except Exception:
                pass
        return 0.0

    @staticmethod
    def _set_ts(key: str, ts: float):
        """Enregistre le timestamp du dernier appel pour une clé."""
        if redis_client:
            try:
                redis_client.set(f"throttle:{key}", str(ts))
            except Exception:
                pass
        
        # Toujours écrire dans le fichier JSON pour le fallback
        data = {}
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, "r") as f:
                    data = json.load(f)
            except Exception:
                pass
        
        data[f"throttle_{key}"] = ts
        try:
            with open(STATUS_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Erreur écriture throttler: {e}")

    @staticmethod
    def wait_for_service(service_name: str, min_gap_seconds: float):
        """
        Bloque jusqu'à ce que le délai minimum soit respecté pour le service donné.
        Le délai est persisté pour survivre aux restarts.
        """
        last_call = Throttler._get_ts(service_name)
        now = time.time()
        elapsed = now - last_call
        
        if elapsed < min_gap_seconds:
            wait_time = min_gap_seconds - elapsed
            logger.info(f"Throttler [{service_name}] : attente de {wait_time:.1f}s...")
            time.sleep(wait_time)
            now = time.time()

        Throttler._set_ts(service_name, now)

    @staticmethod
    def mark_rate_limited(service_name: str, duration: int = 300):
        """Marque un service comme 'bloqué' (429) pour une durée (défaut 5 min)."""
        logger.warning(f"Throttler [{service_name}] : 429 détecté. Blocage global de {duration}s.")
        Throttler._set_ts(f"{service_name}:limited_until", time.time() + duration)

    @staticmethod
    def is_rate_limited(service_name: str) -> bool:
        """Vérifie si le service est actuellement sous le coup d'un cooldown 429."""
        limit_until = Throttler._get_ts(f"{service_name}:limited_until")
        return time.time() < limit_until
