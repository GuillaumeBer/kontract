"""
Module fetcher/listings.py
Simule la récupération de listings individuels pour démonstration du scoring (§4.4).
En production, ce module appellerait l'API Skinport pour les listings réels.
"""

import random

def fetch_listings_mock(market_hash_name: str, median_price: float, n: int = 10) -> list[dict]:
    """
    Génère n listings fictifs autour de la médiane pour démonstration.
    """
    listings = []
    for i in range(n):
        # Prix entre -15% et +15% de la médiane
        price = median_price * (1 + random.uniform(-0.15, 0.15))
        # Float aléatoire
        float_val = random.uniform(0.15, 0.37) # Field-Tested par défaut
        
        listings.append({
            "item_id": f"mock_{i}",
            "market_hash_name": market_hash_name,
            "price": round(price, 2),
            "float_value": round(float_val, 4),
            "lock_days": 0,
            "souvenir": False,
            "stattrak": False,
            "stickers": [] if random.random() > 0.3 else [{"name": "Standard Sticker"}],
            "age_minutes": random.randint(1, 120),
        })
    return listings
