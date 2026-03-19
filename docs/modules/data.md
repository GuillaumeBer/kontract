# Module data/

Gère la base de données SQLite et le chargement des données de structure CS2 depuis ByMykel CSGO-API.

## Fichiers

### `data/models.py`

Définit les 6 tables SQLAlchemy du projet :

| Table | Description |
|-------|-------------|
| `Collection` | Collections CS2 (The Huntsman Collection, etc.) |
| `Skin` | Skins avec rareté, float min/max, StatTrak, market_hash_name |
| `TradeupPool` | Liens input → output possibles pour chaque trade-up |
| `Price` | Prix temps réel par skin et par plateforme |
| `UserAlert` | Profils d'alerte par utilisateur Telegram |
| `Opportunity` | Trade-ups qualifiés détectés par le moteur EV |

### `data/database.py`

- `init_db()` : crée toutes les tables si elles n'existent pas
- `get_session()` : retourne une session SQLAlchemy
- `redis_client` : client Redis optionnel (None si Redis non disponible)

Variables d'environnement :
- `DATABASE_URL` (défaut : `sqlite:///./kontract.db`)
- `REDIS_URL` (défaut : `redis://localhost:6379/0`)

### `data/bymykel.py`

Télécharge et indexe les données de structure CS2 depuis ByMykel CSGO-API.

#### Source

```
GET https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en/collections.json
GET https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en/skins.json
```

#### Constante `RARITY_ORDER`

Ordre des raretés (index = niveau) :
```
0 — rarity_common_weapon    (Consumer Grade, gris)
1 — rarity_uncommon_weapon  (Industrial Grade, bleu clair)
2 — rarity_rare_weapon      (Mil-Spec Grade, bleu)
3 — rarity_mythical_weapon  (Restricted, violet)
4 — rarity_legendary_weapon (Classified, rose)
5 — rarity_ancient_weapon   (Covert, rouge)
```

Un trade-up prend des skins de niveau N et produit un skin de niveau N+1.

#### Fonctions

**`get_output_pool(collection, input_rarity_id) -> list`**

Retourne tous les skins du tier supérieur dans une collection.

```python
from data.bymykel import get_output_pool

outputs = get_output_pool(collection_dict, "rarity_rare_weapon")
# → liste des skins Restricted (violet) de la collection
```

**`build_collections_db() -> dict`**

Télécharge + parse + upsert en BDD. Retourne les stats :
```python
{"collections": 106, "skins": 2622, "tradeup_links": 4407}
```

#### Utilisation

```bash
# Initialisation (première fois)
python -m data.bymykel

# Mise à jour hebdomadaire (via APScheduler dans main.py)
from data.bymykel import build_collections_db
build_collections_db()
```

## Résultats après initialisation

- **106 collections** CS2 chargées
- **2 622 skins** avec raretés, floats et market_hash_name
- **4 407 liens trade-up** input → output indexés
