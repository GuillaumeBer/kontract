# Module engine/

Moteur de calcul EV (Expected Value) et scanner vectorisé de trade-up contracts.

## Fichiers

### `engine/ev_calculator.py`

Implémente la formule EV en 5 étapes (spec §4.3).

#### Types de données

**`InputSkin`**
```python
@dataclass
class InputSkin:
    skin_id: str
    name: str
    collection_id: str
    rarity_id: str
    buy_price: float       # prix d'achat hors frais
    source_buy: str        # "skinport" | "steam"
```

**`OutputSkin`**
```python
@dataclass
class OutputSkin:
    skin_id: str
    name: str
    sell_price: float      # prix de vente attendu ajusté (hors frais), via get_sell_price()
    volume_24h: float      # ventes/jour (score liquidité)
    source_sell: str       # "skinport" | "steam"
    reliability: str       # "stable" | "trending_down" | "trending_up" | "*_price_divergence"
```

**`SellPriceResult`**
```python
@dataclass
class SellPriceResult:
    adjusted_price: float
    reliability: str  # "stable" | "trending_down" | "trending_up" | "*_price_divergence"
```

**`EVResult`**
```python
@dataclass
class EVResult:
    ev_brute: float        # EV avant frais de vente
    ev_nette: float        # EV après tous les frais
    roi: float             # ROI en % = (ev_nette / cout_ajuste) * 100
    cout_ajuste: float     # coût total des 10 inputs + frais achat
    pool_size: int         # nombre d'outputs possibles
    pool_score: float      # 1 / pool_size (haut = pool concentré)
    liquidity_score: float # max volume_24h parmi les outputs
    win_prob: float        # % de chance que l'output > coût ajusté
    outputs: list[dict]    # détail des outputs avec probabilités
```

#### Formule EV

```
ÉTAPE 1 : Probabilités
  prob(output X dans collection A) = (nb_inputs_A / 10) × (1 / nb_outputs_A)

ÉTAPE 2 : EV brute
  EV_brute = Σ (prob_i × prix_vente_output_i)

ÉTAPE 3 : Coût ajusté
  cout_ajuste = Σ prix_input_j × (1 + fee_buy)
  Skinport fee_buy = 5% | Steam fee_buy = 15%

ÉTAPE 4 : EV nette
  EV_nette = EV_brute × (1 - fee_sell) - cout_ajuste
  Skinport fee_sell = 3% | Steam fee_sell = 15%

ÉTAPE 5 : ROI et scoring
  ROI        = (EV_nette / cout_ajuste) × 100
  pool_score = 1 / nb_outputs_total
  liquidity  = max(volume_24h des outputs)
  win_prob   = Σ prob_i où (prix_output_i × (1 - fee_sell)) > cout_ajuste
```

#### `get_sell_price(price_data, steam_data=None) -> SellPriceResult | None`

Détermine le prix de vente ajusté selon 4 règles (spec §4.3). Retourne `None` si les données sont insuffisantes.

**Comportement par cas :**

| Cas | Condition | `adjusted_price` | `reliability` |
|-----|-----------|-----------------|---------------|
| Liquide stable | `volume_7d ≥ 30`, `\|trend\| ≤ 15%` | `avg_7d` | `"stable"` |
| Liquide en baisse | `volume_7d ≥ 30`, `trend < -15%` | `avg_7d × (1 + trend × 0.5)` | `"trending_down"` |
| Liquide en hausse | `volume_7d ≥ 30`, `trend > +15%` | `avg_7d` (inchangé) | `"trending_up"` |
| Peu liquide stable | `volume_30d ≥ 30` | `avg_30d` | `"stable"` |
| Données insuffisantes | volume < 30 sur toutes fenêtres | — | `None` |

**Exemple :**
```python
from engine.ev_calculator import get_sell_price

# Skin en baisse de 20%
r = get_sell_price({"volume_7d": 50, "avg_7d": 8.0, "avg_30d": 10.0, "volume_30d": 100})
# SellPriceResult(adjusted_price=9.0, reliability="trending_down")

# Données insuffisantes
r = get_sell_price({"volume_7d": 5, "avg_7d": 10.0, "volume_30d": 10, "avg_30d": None})
# None → output exclu du scan
```

---

#### Frais par plateforme

| Plateforme | Frais achat | Frais vente |
|-----------|------------|------------|
| Skinport | 5% | 3% |
| Steam | 15% | 15% |

#### Exemple d'utilisation

```python
from engine.ev_calculator import InputSkin, OutputSkin, calculate_ev

inputs = [InputSkin("id", "AK-47 | Blue Laminate", "col-1", "rarity_rare_weapon", 1.50)] * 10
outputs = {
    "col-1": [
        OutputSkin("out-1", "AK-47 | Redline (FT)", 40.0, volume_24h=50),
        OutputSkin("out-2", "M4A4 | X-Ray (FT)", 15.0, volume_24h=20),
    ]
}
result = calculate_ev(inputs, outputs)
# EVResult(ev_nette=4.62, roi=29.3, pool_size=2, win_prob=33.3, ...)
```

---

### `engine/scanner.py`

Scan de toutes les combinaisons de trade-up valides en BDD.

#### `UserFilters`

```python
@dataclass
class UserFilters:
    min_roi: float = 10.0               # ROI minimum (%)
    max_budget: float = 100.0           # budget max pour 10 inputs (€)
    max_pool_size: int = 5              # nb max d'outputs possibles
    min_liquidity: float = 3.0          # volume ventes/jour min sur les outputs
    min_volume_sell_price: int = 30     # ventes min pour fiabilité statistique (plage 10–100)
    exclude_trending_down: bool = False # exclure outputs en baisse > 15% sur 30j
    source_buy: str = "skinport"
    source_sell: str = "skinport"
```

#### `scan_all_opportunities(filters) -> list[dict]`

Scanne toutes les combinaisons mono-collection (10 inputs identiques) :

1. Charge les prix d'achat et de vente depuis la BDD
2. Pour chaque skin avec prix d'achat, vérifie les filtres budget/pool
3. Calcule l'EV via `calculate_ev`
4. Filtre par ROI minimum et liquidité
5. Trie par ROI décroissant

**Résultats MVP** : 1099 combos évalués → **252 opportunités** avec ROI ≥ 5% (sans filtre de liquidité).

Chaque opportunité retournée contient :
```python
{
    "combo_hash": "skin-id:collection-id",
    "input_name": "Galil AR | Hunting Blind",
    "ev_nette": 68.11,
    "roi": 254.4,
    "cout_ajuste": 26.77,
    "pool_size": 5,
    "pool_score": 0.2,
    "liquidity_score": 0.0,  # non nul après fetch Skinport history
    "win_prob": 20.0,
    "jackpot_ratio": 1.5,
    "ev_ajustee": 13.6,
    "kontract_score": 3.2,
    "outputs": [...]   # chaque output inclut "reliability" (stable / trending_down / ...)
}
```

Les outputs dont `get_sell_price()` retourne `None` (volume insuffisant) sont exclus silencieusement. Si `filters.exclude_trending_down=True`, les outputs en baisse > 15% sur 30j sont également exclus.

#### `save_opportunities(opportunities) -> int`

Persiste les opportunités en table `opportunities`. Fait un upsert (update si combo_hash existe déjà).

#### Exemple d'utilisation

```python
from engine.scanner import scan_all_opportunities, UserFilters

filters = UserFilters(min_roi=10, max_budget=100, max_pool_size=5, min_liquidity=3)
opps = scan_all_opportunities(filters)

for opp in opps[:5]:
    print(f"{opp['input_name']}: ROI={opp['roi']:.1f}% EV={opp['ev_nette']:.2f}€")
```

## Performance

Le scan de 1099 combos s'exécute en < 1 seconde. Pour des combinaisons multi-collection (mix d'inputs de collections différentes), l'extension NumPy vectorisée est prévue en V2.
