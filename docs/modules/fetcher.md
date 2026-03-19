# Module fetcher/

Agrégateur de prix temps réel depuis Skinport API et Steam Market API.

## Fichiers

### `fetcher/skinport.py`

Client async pour l'API publique Skinport (aucune authentification requise).

#### Constantes

```python
FEE_BUY = 0.05   # 5% frais acheteur
FEE_SELL = 0.03  # 3% frais vendeur

WEAR_CONDITIONS = [
    "Field-Tested",    # priorité 1 (plus échangé)
    "Minimal Wear",
    "Factory New",
    "Well-Worn",
    "Battle-Scarred",
]
```

#### Fonctions

**`fetch_items(currency="EUR") -> list[dict]`**

Appelle `GET /v1/items?app_id=730&currency=EUR&tradable=0`.
Retourne la liste brute Skinport avec `min_price`, `suggested_price`, `median_price`, `quantity`.

> IMPORTANT : header `Accept-Encoding: br` obligatoire — httpx[brotli] gère la décompression automatiquement.

**`fetch_sales_history(currency="EUR") -> list[dict]`**

Appelle `GET /v1/sales/history?app_id=730&currency=EUR`.
Retourne le volume de ventes sur 24h / 7j / 30j / 90j par skin.

**`_find_best_skinport_match(base_name, price_idx) -> dict | None`**

Cherche le meilleur match Skinport pour un skin sans condition d'usure (format ByMykel).
Tente les conditions dans l'ordre : Field-Tested → Minimal Wear → Factory New → Well-Worn → Battle-Scarred → nom exact.

**`update_prices_from_skinport(threshold=0.005) -> dict`**

Fonction principale de mise à jour :
1. Fetch items + history depuis Skinport
2. Pour chaque skin en BDD, trouve le meilleur match par condition d'usure
3. N'écrit en BDD que si variation > 0.5% vs prix précédent
4. Cache Redis optionnel TTL 300s (`price:skinport:{skin_id}`)

Retourne : `{"updated": 1389, "skipped": N, "not_found": 32}`

#### Rate limit

| Endpoint | Limite | Stratégie MVP |
|----------|--------|---------------|
| `/v1/items` | 8 req / 5 min | 1 appel toutes les 5 min |
| `/v1/sales/history` | 8 req / 5 min | 1 appel toutes les 5 min |

Usage total : **2 req / 5 min = 25% du quota disponible.**

---

### `fetcher/steam.py`

Client pour l'API publique Steam Market.

#### Constantes

```python
FEE_BUY = 0.15   # 15% frais acheteur
FEE_SELL = 0.15  # 15% frais vendeur
```

#### Fonctions

**`fetch_steam_price(market_hash_name, currency=3) -> dict | None`**

Appelle `GET https://steamcommunity.com/market/priceoverview/`.
`currency=3` = EUR. Retourne `lowest_price`, `median_price`, `volume` ou `None` si erreur / rate limit.

**`update_prices_from_steam(skin_ids=None, delay=1.5) -> dict`**

Met à jour les prix Steam pour les skins indiqués (tous si `skin_ids=None`).
Le paramètre `delay` (défaut 1.5s) espace les requêtes pour respecter le rate limit (100 req/5min).

#### Rate limit Steam

100 req / 5 min (100 000 req/jour). Le MVP poll toutes les 10 min sur les skins outputs prioritaires uniquement.

---

## Utilisation

```python
import asyncio
from fetcher.skinport import update_prices_from_skinport
from fetcher.steam import update_prices_from_steam

# Mise à jour Skinport (appelé toutes les 5 min par APScheduler)
stats = asyncio.run(update_prices_from_skinport())

# Mise à jour Steam (appelé toutes les 10 min, skins prioritaires seulement)
stats = asyncio.run(update_prices_from_steam(skin_ids=["skin-123", "skin-456"]))
```

## Résultats observés

- Skinport : **1 389 skins mis à jour** sur 2 622 (les 32 non trouvés sont des skins très rares ou non listés)
- Steam : fonctionne par skin individuel, adapté aux outputs de haute valeur
