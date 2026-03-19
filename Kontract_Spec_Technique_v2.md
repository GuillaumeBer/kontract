# Kontract.gg — Spécification Fonctionnelle & Technique
**CS2 Trade-Up Scanner — SaaS**  
Version 2.0 — Mars 2026

| Délai MVP | Stack principal | Coût données MVP | Lignes code MVP |
|-----------|----------------|-----------------|----------------|
| 3–4 semaines | Python | **0 €** | ~1 500 |

---

## Table des matières

1. [Vision & proposition de valeur](#1-vision--proposition-de-valeur)
2. [Sources de données — 100% gratuit](#2-sources-de-données--100-gratuit)
3. [Architecture technique](#3-architecture-technique)
4. [Spécifications fonctionnelles](#4-spécifications-fonctionnelles)
5. [Stack technique](#5-stack-technique)
6. [Roadmap](#6-roadmap)
7. [Risques & mitigations](#7-risques--mitigations)

---

## 1. Vision & proposition de valeur

Kontract.gg est un SaaS B2C permettant aux traders de skins CS2 d'identifier en temps réel les trade-up contracts à Expected Value (EV) positive. Il intègre les prix Skinport (source officielle gratuite), un score de concentration du pool, le float crafting dans l'EV, et des alertes Telegram/Discord instantanées configurables par seuil de ROI.

> **Proposition de valeur** : *"Trouve les trade-ups profitables CS2 en 0 délai, avec les meilleures sources de prix disponibles, et reçois une alerte Telegram instantanée configurée sur ton seuil de ROI. Tu vois l'opportunité avant tout le monde — y compris les abonnés TradeUpLab."*

### 1.1 Périmètre du MVP (semaines 1–4)

- **Module 1** : Base de données des collections CS2 (ByMykel CSGO-API — statique)
- **Module 2** : Agrégateur de prix temps réel (Skinport API publique + Steam Market API)
- **Module 3** : Moteur de calcul EV avec filtres configurables par utilisateur
- **Module 4** : Dashboard Streamlit + bot Telegram

> **Hors scope MVP** : BUFF163 scraping direct (phase 2), Pricempire API (phase 2 si besoin), float crafting avancé (phase 2), app mobile (phase 3), StatTrak dédié (phase 3).

---

## 2. Sources de données — 100% gratuit

Après analyse complète des APIs disponibles (mars 2026), l'architecture de données du MVP repose exclusivement sur des sources gratuites et légalement claires. Pricempire API a été éliminée du MVP en raison de son coût (119.90$/mois pour seulement 10 000 appels/mois).

### 2.1 Tableau récapitulatif

| Source | Données | Méthode | Fréquence | Coût | Statut légal | Rate limit |
|--------|---------|---------|-----------|------|-------------|-----------|
| ByMykel CSGO-API | Collections, skins, raretés, floats min/max, StatTrak, pool trade-up | JSON statique GitHub Pages | 1x/semaine | 0€ | Option A — usage courant dans l'écosystème | Aucune limite documentée |
| Skinport /v1/items | Prix min/max/moyen/médian + quantité dispo par skin | API REST publique — aucune auth requise | 1x/5 min | 0€ | ✓ Autorisé — API officielle publique | **8 req/5 min** (cache 5 min) |
| Skinport /v1/sales/history | Volume ventes 24h/7j/30j/90j — critère liquidité | API REST publique — aucune auth requise | 1x/5 min | 0€ | ✓ Autorisé — API officielle publique | **8 req/5 min** (cache 5 min) |
| Skinport /v1/sales/out-of-stock | Prix référence skins hors stock | API REST publique — aucune auth requise | 1x/heure | 0€ | ✓ Autorisé | Non documentée — cache 1h |
| Steam Market API | Prix de référence + volume Steam | API publique Valve | 1x/10 min | 0€ | ✓ Autorisé (100k req/jour) | 100 req/5 min |

> **Coût total données MVP : 0€** — Toutes les sources nécessaires au MVP sont gratuites et ne requièrent aucune inscription. Pricempire API (119.90$/mois / 10 000 appels) est mise en réserve pour la phase 2 si des sources additionnelles deviennent nécessaires.

---

### 2.2 ByMykel CSGO-API — source du pool d'outputs

L'API ByMykel (`github.com/ByMykel/CSGO-API`) est un projet open source non officiel qui parse les fichiers de données de Valve (`items_game.txt`, `csgo_english.txt`) et les expose en JSON. C'est la source la plus complète et la plus utilisée dans l'écosystème CS2 pour les données de structure du jeu.

#### Endpoints utilisés

```
# Collections avec skins par rareté — CLEF DU POOL D'OUTPUTS
GET https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en/collections.json

# Tous les skins avec float min/max, rareté, StatTrak, collections
GET https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en/skins.json

# Skins non groupés (chaque condition de wear séparée)
GET https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en/skins_not_grouped.json
```

#### Structure JSON collections.json

```json
{
  "id": "collection-set-community-3",
  "name": "The Huntsman Collection",
  "contains": [
    {
      "id": "skin-1967292",
      "name": "Tec-9 | Isaac",
      "rarity": {
        "id": "rarity_rare_weapon",
        "name": "Mil-Spec Grade",
        "color": "#4b69ff"
      },
      "paint_index": "303"
    }
  ]
}
```

#### Logique de construction du pool d'outputs

```python
# Ordre des raretés — trade-up = tier N → tier N+1
RARITY_ORDER = [
    "rarity_common_weapon",      # Consumer Grade (gris)
    "rarity_uncommon_weapon",    # Industrial Grade (bleu clair)
    "rarity_rare_weapon",        # Mil-Spec Grade (bleu)
    "rarity_mythical_weapon",    # Restricted (violet)
    "rarity_legendary_weapon",   # Classified (rose)
    "rarity_ancient_weapon",     # Covert (rouge)
]

def get_output_pool(collection: dict, input_rarity_id: str) -> list:
    """Retourne tous les skins du tier supérieur dans la collection."""
    next_tier_idx = RARITY_ORDER.index(input_rarity_id) + 1
    next_tier = RARITY_ORDER[next_tier_idx]
    return [
        skin for skin in collection["contains"]
        if skin["rarity"]["id"] == next_tier
    ]

# Exemple : AK-47 Redline (Restricted) dans The Train Collection
# → outputs = tous les Classified (rose) de The Train Collection
# → pool_size = len(outputs)  # critère de concentration
```

#### Statut légal — Option A (choix validé)

Le repo `ByMykel/CSGO-API` ne contient pas de fichier LICENSE explicite. En théorie, tous les droits sont réservés. En pratique, l'intégralité des outils CS2 commerciaux (TradeUpLab, CS2Locker, Pricempire, etc.) utilisent les mêmes données sans que Valve n'ait jamais engagé de procédure. Le risque réel est négligeable pour un outil de calcul d'EV.

> **Option A validée** : Usage des données ByMykel comme le font tous les concurrents directs. Alternative possible en phase 2 : parser directement `items_game.txt` via l'API Steam `ISteamEconomy` pour s'affranchir de toute dépendance tierce.

---

### 2.3 Skinport API — source des prix et de la liquidité

Skinport fournit une API REST publique et officielle, sans inscription ni clé API requise pour les endpoints publics. C'est la source principale de prix pour le moteur EV du MVP.

#### Endpoint /v1/items — prix temps réel

```
GET https://api.skinport.com/v1/items?app_id=730&currency=EUR&tradable=0

Headers: { "Accept-Encoding": "br" }   # OBLIGATOIRE

Rate limit : 8 requêtes par 5 minutes
Cache serveur : 5 minutes (inutile d'appeler plus souvent)
Auth : AUCUNE requise

Réponse par skin : suggested_price, min_price, max_price, mean_price, median_price, quantity
```

#### Endpoint /v1/sales/history — liquidité output

```
GET https://api.skinport.com/v1/sales/history?app_id=730&currency=EUR

Headers: { "Accept-Encoding": "br" }
Rate limit : 8 requêtes par 5 minutes
Cache serveur : 5 minutes
Auth : AUCUNE requise

Réponse par skin :
  last_24_hours: { min, max, avg, median, volume }
  last_7_days:   { min, max, avg, median, volume }
  last_30_days:  { min, max, avg, median, volume }
  last_90_days:  { min, max, avg, median, volume }

volume 24h → liquidity_score — absent chez tous les concurrents
```

#### Calcul du quota Skinport pour le MVP

2 appels/5min × 288 fenêtres/jour × 30 jours = **17 280 appels/mois**. Aucun quota mensuel documenté — la seule contrainte est le rate limit de 8 req/5min. Le MVP utilise 25% du quota disponible.

---

### 2.4 Pricempire API — réservée phase 2

Après analyse des tarifs réels (mars 2026), Pricempire API est exclue du MVP.

| Plan | Prix | Appels/mois | Appels/jour | Prices API | Décision MVP |
|------|------|------------|------------|-----------|-------------|
| Trader (gratuit) | 0€ | 1 000 | 100 | Accès limité | Insuffisant pour scanner |
| **API (développeurs)** | **119.90$/mois** | **10 000** | **1 000** | Accès complet | **Trop cher pour le MVP** |
| Enterprise | 239.90$/mois | 100 000 | 10 000 | Accès complet | Hors budget |

> **Phase 2 uniquement** : Pricempire sera évalué à partir de 200+ abonnés (MRR ~1 800€+). Son principal avantage : agrégation BUFF163 sans scraping direct.

---

## 3. Architecture technique

### 3.1 Vue d'ensemble — 4 modules

| Module | Rôle | Technologie | Complexité | Priorité |
|--------|------|-------------|-----------|---------|
| 1. BDD Collections | Structure statique : collections, raretés, floats, pools trade-up (ByMykel) | Python + SQLite → PostgreSQL | Faible | Semaine 1 |
| 2. Agrégateur prix | Prix toutes les 5 min — Skinport API + Steam Market API | Python + APScheduler + Redis | Modérée | Semaine 2 |
| 3. Moteur EV | Calcul EV de toutes les combinaisons, filtrage, scoring | Python + NumPy (vectorisé) | Faible | Semaine 3 |
| 4. Interface & alertes | Dashboard utilisateur + bot Telegram + notifications | Streamlit (MVP) → React (V2) | Modérée | Semaine 3–4 |

### 3.2 Flux de données — séquence complète

1. Job hebdomadaire : téléchargement `collections.json` + `skins.json` de ByMykel → construction BDD pools d'outputs
2. APScheduler toutes les 5 minutes : appel Skinport `/v1/items` (prix) + `/v1/sales/history` (liquidité)
3. Normalisation : format uniforme (`market_hash_name`, `min_price`, `sell_price`, `volume_24h`, `timestamp`)
4. Cache Redis TTL 5 min + écriture PostgreSQL si variation > 0,5%
5. Moteur EV : scan vectorisé NumPy de toutes les combinaisons (~2–5 sec)
6. Filtrage selon les profils utilisateurs (ROI min, budget max, pool max, liquidité min)
7. Opportunités qualifiées → stockage BDD + push Telegram instantané aux abonnés concernés

---

## 4. Spécifications fonctionnelles

### 4.1 Module 1 — Base de données des collections

#### Construction depuis ByMykel

```python
import requests, json, sqlite3

BASE_URL = "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en"

def build_collections_db():
    collections = requests.get(f"{BASE_URL}/collections.json").json()
    skins       = requests.get(f"{BASE_URL}/skins.json").json()

    # Indexer les skins par id
    skins_idx = {s["id"]: s for s in skins}

    for collection in collections:
        store_collection(collection)
        for skin in collection["contains"]:
            full_skin = skins_idx.get(skin["id"], {})
            store_skin(skin, full_skin, collection["id"])
            # Construire le pool d'outputs
            outputs = get_output_pool(collection, skin["rarity"]["id"])
            for output in outputs:
                store_tradeup_link(skin["id"], output["id"])
```

#### Schéma de base de données

```sql
-- Tables SQLite (MVP) → PostgreSQL (V2)
collections  : id, name, release_date, active

skins        : id, name, weapon, collection_id, rarity_id, rarity_name,
               float_min, float_max, stattrak, market_hash_name

tradeup_pool : input_skin_id, output_skin_id, collection_id
               -- 1 ligne = 1 output possible pour 1 input donné

prices       : skin_id, platform, buy_price, sell_price,
               min_price, median_price, quantity,
               volume_24h, volume_7d, volume_30d,
               avg_24h, avg_7d, avg_30d,
               trend_7d_30d,           -- (avg_7d - avg_30d) / avg_30d
               price_anomaly,          -- booléen : min_price aberrant ?
               high_volatility,        -- booléen : variation 24h > 15% ?
               updated_at

user_alerts  : user_id, min_roi, max_budget, max_pool_size,
               min_liquidity, min_input_qty,
               source_buy, source_sell,
               exclude_trending_down, exclude_high_volatility,
               min_kontract_score, active

opportunities: id, combo_hash,
               inputs_json,            -- liste des inputs retenus
               strategy_used,          -- "pure" | "fillers"
               ev_brute, ev_nette, roi,
               cout_ajuste,
               win_prob,               -- sur prix nets après frais
               pool_size,              -- nb outputs théoriques
               nb_valid_outputs,       -- outputs avec prix fiable
               cv_pond,                -- coefficient de variation pondéré
               liquidity_score,        -- score liquidité output pondéré par prob
               input_liquidity_status, -- liquid / partial / scarce
               price_reliability,      -- worst-case reliability des outputs
               high_volatility,        -- flag volatilité 24h
               kontract_score,         -- score composite final
               created_at
```

---

### 4.2 Module 2 — Agrégateur de prix

#### Gestion du rate limit Skinport

```python
# Rate limit : 8 req / 5 min par endpoint
# Stratégie MVP : 1 appel /v1/items + 1 appel /v1/sales/history toutes les 5 min
# Soit 2 req / 5min = 25% du quota — large marge de sécurité

import asyncio, httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def fetch_skinport_prices():
    async with httpx.AsyncClient() as client:
        # Brotli obligatoire pour /v1/items
        items = await client.get(
            "https://api.skinport.com/v1/items",
            params={"app_id": 730, "currency": "EUR", "tradable": 0},
            headers={"Accept-Encoding": "br"}
        )
        history = await client.get(
            "https://api.skinport.com/v1/sales/history",
            params={"app_id": 730, "currency": "EUR"},
            headers={"Accept-Encoding": "br"}
        )
    return items.json(), history.json()

scheduler = AsyncIOScheduler()
scheduler.add_job(fetch_skinport_prices, "interval", minutes=5)
```

---

### 4.3 Module 3 — Moteur de calcul EV

#### Détermination du prix de vente espéré

Le prix de vente d'un output est calculé via `get_sell_price()` qui applique quatre règles successives : fenêtre temporelle adaptative selon le volume, détection de tendance baissière ou haussière, ajustement conservateur du prix, et cross-check multi-sources à partir de la V1.

La médiane est préférée à la moyenne car elle est naturellement résistante aux outliers (un vendeur listant à 500€ alors que le marché est à 50€ ne déplace pas la médiane). Éliminer les outliers manuellement n'est donc pas nécessaire — à condition que le seuil de volume minimum soit respecté.

**Règle 1 — Fenêtre temporelle adaptative (seuil absolu : 30 ventes)**

On ne fixe pas une fenêtre rigide de 7 ou 30 jours. On choisit la **fenêtre la plus courte qui atteint 30 ventes**, ce qui garantit une médiane statistiquement robuste quelle que soit la liquidité du skin.

```
volume 7j  ≥ 30  → médiane 7j   (skin liquide — 4+ ventes/jour)
volume 30j ≥ 30  → médiane 30j  (skin peu liquide — ~1 vente/jour)
aucune fenêtre   → insufficient_data → exclu du scan
```

Pourquoi 30 ? En dessous, une seule transaction aberrante peut représenter 5–10% du volume et biaiser la médiane de façon significative. Au-dessus de 30, la médiane est stable.

> **Protection contre les skins fantômes** : certaines collections anciennes contiennent des skins théoriquement échangeables via trade-up mais qui n'ont plus aucune liquidité depuis des années (`quantity=0` sur Skinport, `volume_30d=0`). Ces skins doivent déclencher `insufficient_data` — la condition `volume_30d < 30` les filtre naturellement. S'assurer que `volume_30d` est bien à 0 (et non `None`) pour les skins hors stock depuis longtemps.

**Règle 2 — Détection de tendance**

Le biais le plus dangereux : calculer l'EV sur une médiane 7j de 60€ alors que le skin était à 80€ il y a 30 jours et continue de baisser. Dans 2 semaines au moment de vendre, le prix réel sera peut-être 40€.

```python
avg_7d  = history["last_7_days"]["avg"]
avg_30d = history["last_30_days"]["avg"]
trend   = (avg_7d - avg_30d) / avg_30d  # variation relative sur le mois

# Seuils de détection :
# trend < -0.15 → prix en baisse de plus de 15% sur le mois → trending_down
# trend > +0.15 → prix en hausse de plus de 15%             → trending_up
# |trend| ≤ 0.15 → prix stable                              → stable
```

**Règle 3 — Ajustement conservateur du prix**

```python
if trend < -0.15:
    # Pénalité partielle sur la baisse — on ne projette pas la tendance
    # en ligne droite, mais on l'anticipe à 50%
    adjusted_price = base_price * (1 + trend * 0.5)
    reliability = "trending_down"

elif trend > +0.15:
    # Pas de surpondération haussière — approche conservatrice
    # On utilise la médiane telle quelle, sans ajouter la tendance
    adjusted_price = base_price
    reliability = "trending_up"

else:
    adjusted_price = base_price
    reliability = "stable"
```

Le choix d'appliquer la tendance à 50% (et non 100%) est délibérément conservateur : les tendances de prix CS2 ne sont pas linéaires et une baisse passée ne prédit pas parfaitement une baisse future. L'objectif est de pénaliser les skins en chute libre, pas d'être un modèle prédictif.

**Règle 4 — Cross-check multi-sources (V1)**

Skinport représente une fraction du marché mondial. Les prix peuvent diverger de 10 à 30% par rapport à Steam Market ou BUFF163 selon les skins. À partir de la V1, le prix Steam est croisé avec le prix Skinport :

```python
if steam_data:
    divergence = abs(adjusted_price - steam_data["median"]) / adjusted_price
    if divergence > 0.20:
        # Écart > 20% entre Skinport et Steam → utiliser le plus bas
        # et signaler la divergence à l'utilisateur
        adjusted_price = min(adjusted_price, steam_data["median"])
        reliability += "_price_divergence"
```

> À partir de la V2, BUFF163 devient la source de référence principale pour les skins de haute valeur (couteaux, gants), où il concentre l'essentiel de la liquidité mondiale.

**Fonction complète**

```python
def get_sell_price(history: dict, items: dict, steam_data: dict = None) -> tuple:
    """
    Retourne (prix_ajusté, fenêtre, fiabilité) pour un output.
    Retourne (None, None, "insufficient_data") si le skin est exclu du scan.
    """
    vol_7d  = history["last_7_days"]["volume"]  or 0
    vol_30d = history["last_30_days"]["volume"] or 0

    # Règle 1 : fenêtre adaptative
    if vol_7d >= 30:
        base_price = history["last_7_days"]["median"]
        window = "7d"
    elif vol_30d >= 30:
        base_price = history["last_30_days"]["median"]
        window = "30d"
    else:
        return None, None, "insufficient_data"

    # Règle 2 : tendance
    avg_7d  = history["last_7_days"]["avg"]  or base_price
    avg_30d = history["last_30_days"]["avg"] or base_price
    trend   = (avg_7d - avg_30d) / avg_30d if avg_30d else 0

    # Règle 3 : ajustement conservateur
    if trend < -0.15:
        adjusted_price = base_price * (1 + trend * 0.5)
        reliability = "trending_down"
    elif trend > +0.15:
        adjusted_price = base_price
        reliability = "trending_up"
    else:
        adjusted_price = base_price
        reliability = "stable"

    # Règle 4 : cross-check Steam (V1+)
    if steam_data and steam_data.get("median"):
        divergence = abs(adjusted_price - steam_data["median"]) / adjusted_price
        if divergence > 0.20:
            adjusted_price = min(adjusted_price, steam_data["median"])
            reliability += "_price_divergence"

    return adjusted_price, window, reliability
```

> **Règle de rejet** : si `get_sell_price` retourne `"insufficient_data"` pour un output, cet output est **exclu du calcul d'EV** et son poids est redistribué proportionnellement sur les outputs valides. Si tous les outputs d'un pool sont invalides, le trade-up est ignoré par le scanner.

Le champ `reliability` remonte dans le dashboard et dans l'alerte Telegram. Une opportunité `trending_down` déclenchera l'alerte avec un badge d'avertissement visible.

---

#### Float-conditional EV — prix spécifique à la condition de wear

La recherche communautaire confirme que c'est l'alpha n°1 ignoré par tous les outils. L'output float est déterministe — on peut donc calculer la condition de wear exacte de l'output, et utiliser le prix **spécifique à cette condition** plutôt qu'un prix médian générique.

```python
def get_output_wear(avg_norm: float, output_skin: dict) -> str:
    """Détermine la condition de wear de l'output à partir du float calculé."""
    f = output_skin["float_min"] + avg_norm * (output_skin["float_max"] - output_skin["float_min"])

    if f < 0.07:   return "Factory New"
    if f < 0.15:   return "Minimal Wear"
    if f < 0.38:   return "Field-Tested"
    if f < 0.45:   return "Well-Worn"
    return "Battle-Scarred"

def get_float_conditional_price(output_skin: dict, avg_norm: float, skinport_data: dict) -> float:
    """
    Retourne le prix Skinport correspondant à la condition de wear prédite.
    Utilise le market_hash_name avec la condition correcte.
    Exemple : "AWP | Asiimov (Field-Tested)" vs "AWP | Asiimov (Factory New)"
    """
    wear = get_output_wear(avg_norm, output_skin)
    hash_name = f"{output_skin['name']} ({wear})"
    skin_data = skinport_data.get(hash_name)
    return skin_data["median_price"] if skin_data else None
```

L'EV devient ainsi **float-conditional** : pour chaque combinaison d'inputs, on calcule le float de l'output, on détermine sa condition, et on utilise le prix de cette condition. Pour un M4A1-S Player Two où FN vaut 80€ et FT vaut 30€, la différence est massive.

> Float-conditional EV hors scope MVP — intégré en V2 avec les données float min/max de ByMykel.

---

#### Risque du trade hold 7 jours — ajustement de l'EV

La recherche confirme ce risque sous-estimé. Les achats Steam Market sont bloqués 7 jours, et la Trade Protection de juillet 2025 ajoute 7 jours sur les items reçus en P2P.

```python
def apply_hold_discount(ev_nette: float, cout_ajuste: float,
                        hold_days: int = 7,
                        vol_history: dict = None) -> float:
    """
    Ajuste l'EV nette pour tenir compte du coût d'opportunité du trade hold.
    Approche simple : discount sur le capital immobilisé.
    Approche avancée : discount basé sur la volatilité historique.
    """
    # Simple : taux d'opportunité quotidien × jours de hold
    taux_quotidien = 0.005  # 0.5%/jour
    discount_simple = cout_ajuste * taux_quotidien * hold_days

    # Avancé : si on a l'historique de prix sur la période
    if vol_history:
        vol_30d = vol_history.get("price_std_30d", 0)  # écart-type des prix 30j
        risk_premium = cout_ajuste * (vol_30d / 100) * (hold_days / 30)
        discount = max(discount_simple, risk_premium)
    else:
        discount = discount_simple

    return ev_nette - discount

# Pour Skinport (achat direct) : hold_days = 7
# Pour achat P2P + trade : hold_days = 14 (Trade Protection juillet 2025)
```

---

#### Méthode de prix SteamAnalyst — blend temporel pondéré

La recherche identifie SteamAnalyst comme gold standard avec 12 ans de données. Leur approche de blend temporel est plus robuste que notre fenêtre adaptative actuelle pour les skins à volume moyen :

```python
def get_price_steamanalyst_method(history: dict) -> float:
    """
    Blend temporel pondéré — inspiré de SteamAnalyst.
    Plus robuste que la fenêtre adaptative sur les skins à volume moyen (10-99 ventes/j).
    """
    avg_7d  = history["last_7_days"]["avg"]   or 0
    avg_30d = history["last_30_days"]["avg"]  or 0
    avg_60d = history.get("last_60_days", {}).get("avg", avg_30d)  # si disponible
    avg_90d = history["last_90_days"]["avg"]  or avg_30d

    if not avg_7d:
        return None

    prix_blend = (avg_7d * 0.60) + (avg_30d * 0.25) + (avg_60d * 0.10) + (avg_90d * 0.05)

    # Filtrage outliers 3-sigma
    mean = avg_30d
    std  = abs(avg_7d - avg_30d)  # approximation de l'écart-type
    if abs(prix_blend - mean) > 3 * std:
        return avg_30d  # fallback sur la moyenne 30j si outlier détecté

    return prix_blend
```

> Ce blend est utilisé en complément de `get_sell_price()` pour les skins à volume moyen (10–99 ventes/jour). Pour les skins très liquides (100+ ventes/jour), la médiane 7j reste plus précise.

---

#### Sources de prix par phase

| Phase | Source principale | Source secondaire | Référence haute valeur |
|-------|------------------|------------------|----------------------|
| MVP | Skinport (médiane ajustée) | — | — |
| V1 | Skinport (médiane ajustée) | Steam Market (cross-check) | — |
| V2+ | Skinport | Steam Market | BUFF163 (couteaux / gants) |

---

#### Constantes de frais — centralisées et versionnées

```python
# constants.py — à mettre à jour si une plateforme modifie ses frais
# Structure réelle Skinport : frais 0% côté acheteur, 3% côté vendeur uniquement
# Le prix affiché sur Skinport est le prix payé par l'acheteur (pas de frais additionnels)
FEES = {
    "skinport": {"buyer": 0.00, "seller": 0.03},
    "steam":    {"buyer": 0.00, "seller": 0.15},
    "buff163":  {"buyer": 0.025, "seller": 0.025},  # phase 2
}
# Note : sur Steam, les 15% sont payés par le vendeur et inclus dans le prix affiché.
# Sur BUFF163, acheteur et vendeur partagent les frais (2.5% chacun).
# Ces constantes doivent être vérifiées à chaque changement de conditions des plateformes.
```

---

#### Formule EV complète — post-mise à jour octobre 2025

```python
# ÉTAPE 1 : Probabilités selon la composition des 10 inputs
# Exemple : 7 inputs collection A + 3 inputs collection B
prob(output_X in A) = (7/10) × (1 / nb_outputs_tier_sup_A)
prob(output_Y in B) = (3/10) × (1 / nb_outcomes_tier_sup_B)

# ÉTAPE 2 : Prix de vente de chaque output via get_sell_price()
# Les outputs "insufficient_data" sont exclus
# Leurs probabilités sont renormalisées sur les outputs valides
prix_i, window_i, reliability_i = get_sell_price(history_i, items_i, steam_i)

# ÉTAPE 2b : Détection haute volatilité (variation 24h > 15%)
# Sécurité contre les MAJ Valve et événements de marché brutaux
vol_24h_change = abs(avg_24h_i - avg_7d_i) / avg_7d_i if avg_7d_i else 0
if vol_24h_change > 0.15:
    reliability_i += "_high_volatility"
    prix_i *= 0.85  # pénalité conservatrice de 15% sur le prix de vente espéré

# ÉTAPE 3 : EV brute (outputs valides uniquement, proba renormalisées)
EV_brute = Σ (prob_i_normalisée × prix_i)

# ÉTAPE 4 : Coût ajusté selon plateforme achat
# Frais acheteur depuis FEES[platform]["buyer"]
# Skinport buyer = 0% (prix affiché = prix payé)
# Steam buyer = 0% (frais inclus dans le prix affiché, supportés par le vendeur)
# BUFF163 buyer = 2.5% (ajouté au prix affiché)
frais_achat = FEES[source_achat]["buyer"]
cout_ajuste = Σ prix_input_j × (1 + frais_achat)
# ⚠️  (1 + frais_achat) et non (1 - frais_achat) :
#     les frais acheteur s'ajoutent au prix, ils ne le réduisent pas

# ÉTAPE 5 : EV nette après frais de vente
# Frais vendeur depuis FEES[platform]["seller"]
frais_vente = FEES[source_vente]["seller"]
EV_nette = EV_brute × (1 - frais_vente) - cout_ajuste

# ÉTAPE 6 : ROI et métriques scoring
ROI               = (EV_nette / cout_ajuste) × 100
pool_score        = 1 / nb_outcomes_total
liquidity         = volume_output_24h
# win_prob : comparaison sur prix NET après frais de vente (corrigé)
win_prob          = Σ prob_i où prix_i × (1 - frais_vente) > cout_ajuste
price_reliability = worst_case(reliability_i for all outputs)
# flag haute volatilité si au moins un output est marqué high_volatility
high_volatility   = any("high_volatility" in r for r in reliability_list)
```

---

#### Critères de filtrage — configurables par utilisateur

| Critère | Défaut | Plage | Source données | Impact |
|---------|--------|-------|---------------|--------|
| ROI minimum | 10% | 5–50% | Moteur EV | Filtre principal de rentabilité |
| Pool max (nb outcomes) | 5 | 1–20 | ByMykel collections | Concentration — différenciateur clé |
| Volume min output (ventes/j) | 3 | 1–50 | Skinport /v1/sales/history | Liquidité à la revente |
| Budget max inputs | 100 € | 10–10 000 € | Skinport /v1/items | Capital max par trade-up |
| Source prix achat | Skinport | Skinport / Steam | Skinport /v1/items | Impact sur le coût ajusté |
| Source prix vente | Skinport | Skinport / Steam | Skinport /v1/items | Impact sur l'EV nette |
| Volume min prix vente | 30 ventes | 10–100 | Skinport /v1/sales/history | Fiabilité statistique de la médiane |
| Exclure tendance baissière | Non | Oui / Non | Moteur EV | Filtre les outputs en chute > 15%/mois |
| Exclure haute volatilité | Non | Oui / Non | Moteur EV | Filtre les outputs avec variation 24h > 15% |
| Kontract Score minimum | 5.0 | 0–50 | Moteur EV | Filtre composite — remplace les filtres individuels pour les utilisateurs avancés |

---

### 4.4 Module 3 — Sélection et gestion des inputs

#### Contraintes de composition — règles Valve

Avant tout calcul, le scanner vérifie que la composition des inputs est valide. Un trade-up invalide est rejeté silencieusement.

| Règle | Détail |
|-------|--------|
| Tier identique | Les 10 inputs doivent être exactement du même tier de rareté |
| StatTrak homogène | Impossible de mélanger StatTrak et non-StatTrak — les 10 doivent être du même type |
| Pas de Souvenir | Les skins Souvenir ne peuvent pas être utilisés comme inputs |
| Cas Covert spécial | Pour Covert → couteaux/gants : 5 inputs seulement (règle post-octobre 2025) |
| Collections mixtes | Un input peut venir de n'importe quelle collection du bon tier, mais chaque collection ajoutée dilue les probabilités vers ses propres outputs |

---

#### Stratégies de sélection des inputs

Pour un output cible donné, deux stratégies sont calculées en parallèle. Le scanner présente les deux avec leur ROI respectif.

**Stratégie A — Collection pure**

Les 10 inputs viennent tous de la même collection que l'output cible. Probabilité maximale d'obtenir l'output voulu.

```
prob(output_cible) = 1 / nb_outputs_tier_sup_collection
cout_total         = 10 × min_price(input_le_moins_cher_de_la_collection)
```

**Stratégie B — Fillers**

7 inputs de la collection cible + 3 inputs d'une collection "filler" très bon marché. Le coût total baisse, la probabilité d'obtenir l'output cible aussi.

```
prob(output_cible) = 0.7 × (1 / nb_outputs_tier_sup_cible)
cout_total         = 7 × prix_input_cible + 3 × prix_filler
```

Les collections classiquement utilisées comme fillers (Italy, Lake, Safehouse, Train) ont des skins de bas tier peu coûteux et des outputs de tier supérieur peu désirables.

> **Critère de sélection des fillers post-octobre 2025 :** la mise à jour a fondamentalement changé ce qui fait un bon filler. Avant, on cherchait des collections avec peu d'outcomes au tier supérieur (pour diluer le moins possible). Maintenant, le critère principal est le **float range le plus large possible (idéal : 0–1)**, car la normalisation universelle rend l'ancien avantage des float caps restreints contre-productif. Un filler avec float range 0–1 a toujours un impact neutre sur le float output. Les fillers actuellement populaires post-update : SG 553 Cyberforce (Kilowatt), Dual Berettas Hideout, MP5-SD Focus (Genesis).

Le scanner choisit la stratégie qui **maximise le ROI final**, pas nécessairement celle qui minimise le coût brut.

---

#### Prix d'achat des inputs

Pour le coût des inputs, on utilise `min_price` de Skinport `/v1/items` — pas la médiane. La raison : on veut le coût **réel d'acquisition minimum**, c'est-à-dire le listing le moins cher disponible à l'instant T.

**Détection d'anomalie sur min_price**

Avant d'utiliser `min_price`, on vérifie qu'il n'est pas aberrant (erreur de listage, manipulation) :

```python
def is_price_anomaly(min_price: float, median_price: float) -> bool:
    """
    Détecte un min_price anormal par rapport à la médiane.
    Retourne True si le prix doit être ignoré.
    """
    if not median_price or median_price == 0:
        return True
    ratio = min_price / median_price
    return ratio < 0.5 or ratio > 2.0
    # < 50% de la médiane → listage probablement erroné ou vente urgente isolée
    # > 200% de la médiane → anomalie inversée (rare mais possible)

def get_input_price(skin_items: dict) -> float:
    """Retourne le prix d'achat fiable pour un input."""
    min_price    = skin_items.get("min_price")
    median_price = skin_items.get("median_price")

    if min_price and not is_price_anomaly(min_price, median_price):
        return min_price        # cas nominal
    elif median_price:
        return median_price     # fallback sur la médiane si min_price aberrant
    else:
        return None             # skin sans prix → exclu du scan
```

| Plateforme | Frais acheteur | Impact sur EV | Disponible MVP |
|-----------|---------------|--------------|----------------|
| Skinport | 5% | Référence | ✓ |
| Steam Market | 15% | −10% sur l'EV nette | ✓ |
| BUFF163 | 2.5% | +2.5% sur l'EV nette | Phase 2 |

L'impact est direct. Sur un panier d'inputs à 100€ de prix marché :

```
Achat Skinport  : cout_ajuste = 100 × (1 - 0.05) = 95.00€
Achat Steam     : cout_ajuste = 100 × (1 - 0.15) = 85.00€
Achat BUFF163   : cout_ajuste = 100 × (1 - 0.025) = 97.50€
```

Acheter sur Steam plutôt que BUFF163 coûte effectivement 12.5€ de plus sur 100€ d'inputs — une différence qui peut transformer une opportunité profitable en perte nette.

---

#### Float des inputs — levier de profit avancé

Le float de l'output est **entièrement déterministe** à partir des floats des inputs. C'est le levier le plus puissant et le plus ignoré par les outils concurrents.

**Formule post-octobre 2025 :**

```python
# 1. Normaliser le float de chaque input sur son propre range [0, 1]
float_norm_i = (float_input_i - float_min_skin_i) / (float_max_skin_i - float_min_skin_i)

# 2. Moyenne des floats normalisés
avg_norm = mean(float_norm_i for i in range(10))  # ou 5 pour les Covert

# 3. Projeter sur le range de l'output cible
float_output = float_min_output + (float_max_output - float_min_output) × avg_norm
```

**Float crafting — logique économique :**

Pour viser un output Factory New (float < 0.07), il faut que `avg_norm` soit suffisamment bas, ce qui implique d'acheter des inputs avec des floats bas — généralement plus chers.

```python
# Question : le surcoût des inputs FN est-il compensé par le premium de l'output FN ?
premium_output = prix_output_FN / prix_output_FT  # souvent 2× à 5× selon le skin
surcoût_inputs = prix_inputs_FN / prix_inputs_quelconque  # souvent +15% à +40%

# Si premium_output > surcoût_inputs → float crafting rentable
```

**Calcul en parallèle — deux EV par opportunité :**

```python
# EV standard — inputs au min_price sans contrainte de float
ev_standard, roi_standard = calculate_ev(
    inputs=select_cheapest(candidates, n=10),
    output=output_target
)

# EV float crafting — inputs avec float bas pour viser FN sur l'output
ev_crafted, roi_crafted = calculate_ev(
    inputs=select_cheapest_low_float(candidates, n=10, target_avg_norm=0.05),
    output=output_target,
    output_condition="Factory New"
)
```

Le dashboard affiche les deux résultats côte à côte. L'utilisateur choisit selon son budget et son appétit pour la stratégie avancée.

> Le float crafting est hors scope MVP. Il est intégré en V2 avec les données de float min/max issues de ByMykel `skins.json`.

---

#### Fonction de sélection des inputs optimaux

```python
def find_optimal_inputs(
    output_target: dict,
    collection: dict,
    tier: str,
    skinport_prices: dict,
    strategy: str = "best_roi"   # "pure" | "fillers" | "best_roi"
) -> dict:
    """
    Retourne les inputs optimaux selon les deux stratégies,
    avec et sans float crafting (V2+).
    """
    candidates = get_skins_by_tier(collection, tier)

    # Stratégie A : collection pure, inputs les moins chers
    inputs_pure = sorted(
        candidates,
        key=lambda s: skinport_prices[s["id"]]["min_price"]
    )[:10]

    # Stratégie B : 7 inputs collection cible + 3 fillers
    fillers      = get_cheapest_fillers(tier, exclude=collection["id"])[:3]
    inputs_mixed = sorted(
        candidates,
        key=lambda s: skinport_prices[s["id"]]["min_price"]
    )[:7] + fillers

    # Calculer EV et ROI pour chaque stratégie
    results = {}
    for label, inputs in [("pure", inputs_pure), ("mixed", inputs_mixed)]:
        ev, roi = calculate_ev(inputs, output_target, skinport_prices)
        results[label] = {
            "inputs": inputs,
            "cout_total": sum(skinport_prices[s["id"]]["min_price"] for s in inputs),
            "ev_nette": ev,
            "roi": roi,
        }

    # Retourner la meilleure stratégie selon le ROI
    best = max(results, key=lambda k: results[k]["roi"])
    return {"best": best, "strategies": results}
```

---

#### Validation pré-trade-up

Avant d'afficher une opportunité à l'utilisateur, le scanner valide :

```python
def validate_tradeup(inputs: list, output_target: dict) -> tuple[bool, str]:
    tiers    = {s["rarity"]["id"] for s in inputs}
    stattrak = {s["stattrak"] for s in inputs}

    if len(tiers) > 1:
        return False, "tiers_mixtes"
    if len(stattrak) > 1:
        return False, "stattrak_mixte"
    if any(s.get("souvenir") for s in inputs):
        return False, "souvenir_interdit"
    if output_target["rarity"]["id"] == "rarity_ancient_weapon" and len(inputs) != 5:
        return False, "covert_requires_5_inputs"

    return True, "valid"
```

---

### 4.5 Module 3 — Liquidité des inputs

La liquidité des inputs est aussi importante que celle des outputs, mais dans le sens inverse : elle détermine si l'opportunité est **exécutable** à un prix réaliste. L'ignorer crée un biais optimiste systématique sur le coût ajusté.

#### Trois problèmes concrets si on l'ignore

**Problème 1 — Le min_price est un leurre**

`min_price = 3.50€` sur Skinport signifie qu'une seule unité est disponible à ce prix. Si on en a besoin de 10, les suivantes coûteront 4.20€, 4.80€, 5.10€... Le coût réel du panier est significativement plus élevé que `10 × min_price`.

```python
# Ce que le scanner naïf calcule :
cout_naif = 10 × min_price                    # faux si quantity < 10

# Ce qu'il faudrait calculer :
cout_reel = sum(sorted_prices[:10])           # somme des 10 listings disponibles
# → impossible avec l'API publique Skinport (pas de liste de prix individuels)
# → on utilise une estimation conservatrice à la place (voir ci-dessous)
```

**Problème 2 — Le temps d'exécution**

Sur un input peu liquide, acheter 10 unités peut prendre plusieurs jours. Pendant ce temps, les prix bougent. Une opportunité à +15% EV calculée aujourd'hui peut être à +3% au moment du 10ème achat.

**Problème 3 — Le spread bid/ask**

Sur les skins peu liquides, l'écart entre `min_price` (ask) et le prix d'exécution réel peut atteindre 20–30%, une friction cachée absente du calcul d'EV standard.

---

#### Estimation du coût réel du panier d'inputs

L'API publique Skinport retourne `quantity` (nombre d'unités disponibles) mais pas la liste des prix individuels. On utilise une heuristique basée sur `quantity`, `min_price` et `median_price` :

```python
def check_input_liquidity(skin_items: dict, qty_needed: int = 10) -> dict:
    """
    Estime le coût réel d'achat de qty_needed unités et évalue la liquidité.
    Retourne un statut et un coût estimé corrigé pour le calcul d'EV.
    """
    quantity     = skin_items.get("quantity", 0)
    min_price    = skin_items.get("min_price")
    median_price = skin_items.get("median_price")

    if quantity == 0 or min_price is None:
        return {"liquidity_status": "out_of_stock", "estimated_cost": None}

    if quantity >= qty_needed:
        # Stock suffisant — médiane comme estimation conservatrice du panier complet
        # (les premières unités seront au min_price, les suivantes au-dessus)
        estimated_cost   = median_price * qty_needed
        liquidity_status = "liquid"

    elif quantity >= qty_needed // 2:
        # Stock partiel — interpolation entre min et median
        estimated_cost   = (min_price + median_price) / 2 * qty_needed
        liquidity_status = "partial"

    else:
        # Très peu de stock — pénalité de 20% sur la médiane
        estimated_cost   = median_price * qty_needed * 1.20
        liquidity_status = "scarce"

    return {
        "quantity_available": quantity,
        "qty_needed":         qty_needed,
        "estimated_cost":     estimated_cost,
        "liquidity_status":   liquidity_status,
    }
```

> **Règle de rejet** : si `liquidity_status == "out_of_stock"` sur un input nécessaire, l'opportunité est **rejetée du scan** — elle n'est pas exécutable.

---

#### Intégration dans le calcul du coût ajusté

```python
# Avant (naïf — sous-estime systématiquement le coût)
cout_ajuste = 10 × min_price × (1 - frais_achat)

# Après (réaliste — prend en compte la profondeur du carnet d'ordres)
input_check = check_input_liquidity(skin_items, qty_needed=10)

if input_check["liquidity_status"] == "out_of_stock":
    return None  # opportunité rejetée

cout_ajuste = input_check["estimated_cost"] × (1 - frais_achat)
```

---

#### Signal de liquidité complémentaire — volume de ventes

Le volume de ventes de l'input sur 24h (depuis `/v1/sales/history`) est un indicateur indépendant de la liquidité à l'achat : un skin qui se vend beaucoup est aussi un skin qu'on trouve facilement à acheter.

```python
vol_24h = history["last_24_hours"]["volume"] or 0

if vol_24h >= 5:
    input_liquidity_signal = "high"    # toujours du stock à prix raisonnable
elif vol_24h >= 1:
    input_liquidity_signal = "medium"  # achat possible, prévoir 1–3 jours
else:
    input_liquidity_signal = "low"     # risque de prix d'exécution élevé
```

Ce signal est affiché dans le dashboard à titre informatif — il n'exclut pas automatiquement l'opportunité, mais aide l'utilisateur à évaluer la difficulté d'exécution.

---

#### Comparaison liquidité input vs output

Les deux biais vont dans le même sens (surestimation de l'EV) et se cumulent si on les ignore tous les deux.

| | Input (achat) | Output (vente) |
|--|--|--|
| Ce qu'on mesure | Peut-on acheter 10 unités à un prix réaliste ? | Peut-on vendre à la médiane calculée ? |
| Donnée principale | `quantity` disponible + `vol_24h` | `volume_7j` ou `volume_30j` |
| Seuil de rejet | `quantity == 0` | `volume_7j < 30` et `volume_30j < 30` |
| Correction si liquide | `median × 10` au lieu de `min × 10` | Médiane ajustée par la tendance |
| Effet si ignoré | Coût sous-estimé → EV surestimée | Prix vente surestimé → EV surestimée |

---

#### Nouveau critère de filtrage utilisateur

| Critère | Défaut | Plage | Source données | Impact |
|---------|--------|-------|---------------|--------|
| Volume min input (ventes/j) | 1 | 0–20 | Skinport /v1/sales/history | Filtre les inputs trop difficiles à acheter |
| Quantité min input disponible | 10 | 1–50 | Skinport /v1/items (`quantity`) | Garantit que le panier est exécutable immédiatement |

Un utilisateur conservateur exigera `quantity ≥ 10` pour s'assurer de pouvoir acheter tous les inputs en une fois au prix affiché. Un utilisateur patient qui échelonne ses achats sur plusieurs jours peut descendre à `quantity ≥ 3`.

---

### 4.6 Module 3 — Kontract Score

Le Kontract Score est un indicateur composite de 0 à +∞ (sans borne supérieure théorique) qui synthétise toutes les dimensions d'une opportunité en un seul chiffre. C'est le **critère de tri par défaut** du dashboard et la valeur affichée en tête de chaque alerte Telegram.

#### Formule de base (implémentée)

```python
# ── NOTE ARCHITECTURALE : suppression du double-comptage win_prob × EV ──────
# L'ancienne formule `ev_ajustee = ev_nette × win_prob` crée un double-comptage :
# l'EV intègre DÉJÀ implicitement les probabilités (c'est une somme Σ prob_i × prix_i).
# Multiplier ensuite par win_prob surpondère les trades à haute probabilité même si
# leur EV nette est faible, et pénalise injustement les pools légitimement asymétriques.
# → Remplacement par un analogue Sharpe ratio : EV_nette / CV_pondéré

# ÉTAPE 1 : Variance pondérée — mesure l'asymétrie réelle du pool
mean_pond = Σ (prob_i × prix_i)                          # espérance des prix
var_pond  = Σ (prob_i × (prix_i - mean_pond)²)            # variance pondérée
cv_pond   = sqrt(var_pond) / mean_pond if mean_pond else 1 # coeff. de variation

# CV pondéré vs jackpot_ratio : un output à 500€ (prob 2%) + neuf à 10€ (prob 98%)
# jackpot_ratio = 500/54 ≈ 9.3  → pénalité injustifiée (EV dominée par les 10€)
# cv_pond ≈ 0.7                 → pénalité proportionnelle à la variance réelle ✓

# ÉTAPE 2 : Score risque — analogue Sharpe (EV / dispersion)
# win_prob reste calculé pour l'affichage et le dashboard, mais n'entre plus
# dans le score pour éviter le double-comptage
win_prob     = Σ prob_i où prix_i × (1 - frais_vente) > cout_ajuste  # affichage uniquement
floor_value  = min(prix_i for i in outputs) × (1 - frais_vente)      # pire outcome net
floor_ratio  = floor_value / cout_ajuste                               # % récupéré au pire cas
score_risque = ev_nette / sqrt(max(cv_pond, 0.01))

# ÉTAPE 3 : Bonus liquidité output — pondéré par probabilité
liquidity_score_output = sum(prob_i × volume_7d_i for i in outputs) / 7
bonus_liquidite_output = ln(1 + liquidity_score_output)

# ÉTAPE 4 : Discount trade hold (risque de dépréciation pendant 7–14 jours)
# taux_opportunité = 0.5% par jour (approximation conservatrice du coût d'opportunité)
# nb_jours_hold = 7 (Steam Market) ou 14 (achat P2P + trade protection juillet 2025)
taux_opp_quotidien = 0.005
nb_jours_hold      = opportunity.get("hold_days", 7)
hold_discount      = 1 - (taux_opp_quotidien * nb_jours_hold)  # ex: 0.965 pour 7j

# ÉTAPE 5 : Score final de base
kontract_score_base = score_risque * (1 + bonus_liquidite_output) * hold_discount
```

---

#### Enrichissement — intégration de la liquidité des inputs

La formule de base n'intègre pas les inputs. Deux corrections sont ajoutées sans modifier la structure existante.

**Correction 1 — Liquidité output pondérée par les probabilités**

Le `max(volume_7d)` actuel est optimiste : si seul le jackpot (faible probabilité) est liquide, le score bénéficie de sa liquidité de façon injustifiée. On remplace par une moyenne pondérée par les probabilités de chaque output.

```python
# Avant — optimiste
liquidity_score = max(volume_7d_i for i in outputs) / 7

# Après — pondéré par probabilité
liquidity_score_output = sum(prob_i × volume_7d_i for i in outputs) / 7
# → si le jackpot (prob=5%) est le seul output liquide,
#   il contribue faiblement au score de liquidité
```

**Correction 2 — Facteur d'exécutabilité des inputs**

```python
# Basé sur input_liquidity_status retourné par check_input_liquidity()
input_exec_factor = {
    "liquid":   1.00,   # quantity >= 10 — achat immédiat au prix calculé
    "partial":  0.75,   # quantity >= 5  — coût légèrement sous-estimé
    "scarce":   0.40,   # quantity < 5   — exécution risquée et lente
    # "out_of_stock" → opportunité rejetée avant ce calcul
}.get(input_liquidity_status, 0.40)
```

**Correction 3 — Bonus vitesse d'exécution des inputs**

```python
# Goulot d'étranglement : l'input le moins liquide dicte la vitesse d'exécution
vol_24h_inputs_min = min(vol_24h_i for i in inputs)
input_speed_bonus  = ln(1 + vol_24h_inputs_min)
# Pondéré à 15% — bonus secondaire, ne domine pas le score
```

---

#### Formule enrichie complète

```python
def calculate_kontract_score(opportunity: dict) -> float:
    """
    Kontract Score v3 — intègre:
    - Sharpe ratio (EV/CV) au lieu du double-comptage win_prob × EV
    - Liquidité inputs/outputs pondérée par probabilité
    - Discount trade hold 7j
    - Pénalité haute volatilité
    - Floor ratio (pire outcome / coût)
    - Recipe velocity detection
    Pas de borne supérieure théorique. Tri par ordre décroissant.
    """
    from math import sqrt, log

    outputs                = opportunity["outputs"]   # [{prob, prix, vol_7d, reliability}]
    ev_nette               = opportunity["ev_nette"]
    cout_ajuste            = opportunity["cout_ajuste"]
    frais_vente            = opportunity["frais_vente"]
    input_liquidity_status = opportunity["input_liquidity_status"]
    vol_24h_inputs         = opportunity["vol_24h_inputs"]
    hold_days              = opportunity.get("hold_days", 7)
    input_price_trend      = opportunity.get("input_price_trend_7d", 0.0)  # recipe velocity

    prix_outputs = [o["prix"] for o in outputs]

    # ── win_prob — AFFICHAGE UNIQUEMENT (ne rentre plus dans le score) ─
    win_prob = sum(
        o["prob"] for o in outputs
        if o["prix"] * (1 - frais_vente) > cout_ajuste
    )

    # ── CV pondéré (analogue Sharpe) ────────────────────────────────────
    mean_pond = sum(o["prob"] * o["prix"] for o in outputs)
    var_pond  = sum(o["prob"] * (o["prix"] - mean_pond) ** 2 for o in outputs)
    cv_pond   = sqrt(var_pond) / mean_pond if mean_pond > 0 else 1
    score_risque = ev_nette / sqrt(max(cv_pond, 0.01))

    # ── Floor ratio — protection contre le pire cas ──────────────────────
    floor_value = min(o["prix"] for o in outputs) * (1 - frais_vente)
    floor_ratio = floor_value / cout_ajuste if cout_ajuste > 0 else 0
    # floor_ratio < 0.20 → peut perdre > 80% → pénalité supplémentaire
    floor_factor = 1.0 if floor_ratio >= 0.20 else (0.5 + floor_ratio * 2.5)

    # ── Liquidité output pondérée par probabilité ────────────────────────
    liq_out = sum(o["prob"] * o["vol_7d"] for o in outputs) / 7
    bonus_liq_out = log(1 + liq_out)

    # ── Trade hold discount ──────────────────────────────────────────────
    taux_opp_quotidien = 0.005   # 0.5%/jour coût d'opportunité
    hold_discount = max(0.5, 1 - taux_opp_quotidien * hold_days)

    # ── Inputs — exécutabilité et vitesse ───────────────────────────────
    input_exec_factor = {
        "liquid":  1.00,
        "partial": 0.75,
        "scarce":  0.40,
    }.get(input_liquidity_status, 0.40)

    vol_24h_min       = min(vol_24h_inputs)
    input_speed_bonus = log(1 + vol_24h_min)

    # ── Recipe velocity — pénalité si inputs déjà en hausse ─────────────
    # Si les inputs ont monté de >10% sur 7j, le trade-up est probablement
    # déjà connu — la fenêtre de profit se referme
    if input_price_trend > 0.10:
        velocity_penalty = max(0.5, 1 - input_price_trend)
    else:
        velocity_penalty = 1.0

    # ── Pénalité haute volatilité ────────────────────────────────────────
    volatility_factor = 0.70 if any(
        "high_volatility" in o.get("reliability", "") for o in outputs
    ) else 1.00

    # ── Score final ──────────────────────────────────────────────────────
    kontract_score = (
        score_risque
        * floor_factor
        * (1 + bonus_liq_out)
        * hold_discount
        * input_exec_factor
        * (1 + 0.15 * input_speed_bonus)
        * velocity_penalty
        * volatility_factor
    )

    return round(kontract_score, 2), {
        "win_prob":       round(win_prob, 3),    # affiché dans l'UI
        "floor_ratio":    round(floor_ratio, 3), # affiché dans l'UI
        "cv_pond":        round(cv_pond, 3),
        "hold_days":      hold_days,
        "velocity_alert": input_price_trend > 0.10,
    }
```

---

#### Exemples chiffrés

**Opportunité A — Solide et exécutable**
ROI 18%, inputs liquides (qty=40, vol_24h=8), output 40 ventes/7j, pool 3 équilibré

```
ev_nette=9€, win_prob=0.85, jackpot_ratio=1.4, vol_24h_min=8
ev_ajustee    = 9 × 0.85 = 7.65
score_risque  = 7.65 / √1.4 = 6.46
liquidity_out = (0.33×40 + 0.33×35 + 0.33×38) / 7 = 5.38
bonus_out     = ln(1 + 5.38) = 1.87
input_exec    = 1.00  (liquid)
speed_bonus   = ln(1 + 8) = 2.20

kontract_score = 6.46 × 1.00 × (1 + 1.87) × (1 + 0.15 × 2.20) = 6.46 × 2.87 × 1.33 = 24.7
```

**Opportunité B — ROI élevé mais risquée**
ROI 35%, inputs scarces (qty=2, vol_24h=0.3), output 8 ventes/7j, pool jackpot asymétrique

```
ev_nette=18€, win_prob=0.45, jackpot_ratio=8.5, vol_24h_min=0.3
ev_ajustee    = 18 × 0.45 = 8.10
score_risque  = 8.10 / √8.5 = 2.78
liquidity_out = (0.05×8 + 0.95×1) / 7 = 0.19   ← jackpot pondéré à 5%
bonus_out     = ln(1 + 0.19) = 0.17
input_exec    = 0.40  (scarce)
speed_bonus   = ln(1 + 0.3) = 0.26

kontract_score = 2.78 × 0.40 × (1 + 0.17) × (1 + 0.15 × 0.26) = 2.78 × 0.40 × 1.17 × 1.04 = 1.35
```

Malgré un ROI presque deux fois supérieur, l'opportunité B obtient un Kontract Score **18× plus bas** que l'opportunité A. Le score reflète correctement qu'elle est difficile à exécuter, peu liquide, et très asymétrique.

---

#### Tableau récapitulatif des évolutions — recherche communautaire

| # | Problème identifié | Source | Avant | Après |
|---|---|---|---|---|
| 1 | Double-comptage win_prob × EV | Analyse communautaire | `ev_nette × win_prob / cv` | `ev_nette / cv` (Sharpe ratio) — win_prob affiché uniquement |
| 2 | Floor value absent | Communauté (piège perte totale) | Absent | `floor_ratio = min_output_net / cout` → facteur multiplicateur |
| 3 | Trade hold 7j non modélisé | CSDelta, communauté | Absent | Discount `1 - 0.5%/jour × nb_jours` |
| 4 | Recipe velocity | TradeUpSpy reviews | Absent | Pénalité si inputs +10% en 7j |
| 5 | Direction frais acheteur | Revue interne | `× (1 - frais)` | `× (1 + frais)` |
| 6 | win_prob sur prix bruts | Revue interne | Prix brut | Prix net `× (1 - frais_vente)` |
| 7 | CV pondéré vs jackpot_ratio | Revue interne | `max/mean` | `sqrt(var_pond) / mean_pond` |
| 8 | Liquidité output max → pondérée | Revue interne | `max(vol_7d)` | `Σ(prob × vol_7d)` |
| 9 | Exécutabilité inputs absente | Revue interne | Absent | `× input_exec_factor` |
| 10 | Anomalie min_price | Revue interne | Non détectée | `is_price_anomaly()` |
| 11 | Haute volatilité 24h | Revue interne | Non détectée | Flag + `× 0.70` |
| 12 | Frais centralisés | Revue interne | Commentaires éparses | Dict `FEES` versionné |

---

#### Affichage dans le dashboard et les alertes

Le Kontract Score est le **critère de tri par défaut**. Dans le dashboard :

```
Score   Trade-up                              ROI    Tendance  Pool
24.7    AK-47 Redline FT → Fever Dream FN    +18%   🟢 stable  3
18.3    M4A4 Desolate → Asiimov FT           +22%   🟢 stable  2
 1.4    FAMAS Commemoration → Dragon King BS  +35%   🔴 ↓prix   6
```

Dans l'alerte Telegram :

```
🎯 Kontract Score : 24.7
AK-47 Redline FT → AWP Fever Dream FN
ROI : +18% | EV nette : +9.20€ | win_prob : 85% | floor : 42%
Pool : 3 outcomes | Inputs : 🟢 liquid (qty=40) | Kelly : 2.3% du bankroll
Output liquidité : 40 ventes/7j | Prix : 🟢 stable | Répétable 8×
```

---

### 4.7 Module 3 — Détections avancées et métriques complémentaires

#### Recipe velocity — détection de trade-up viral

Dès qu'un trade-up profitable devient connu, les prix des inputs bondissent de 10–20% en quelques heures et la marge disparaît. Kontract.gg détecte ce signal et alerte avant saturation.

```python
def detect_recipe_velocity(input_skins: list, skinport_history: dict) -> dict:
    """Détecte si les inputs d'un trade-up sont déjà en hausse rapide."""
    trends = []
    for skin in input_skins:
        h = skinport_history.get(skin["market_hash_name"], {})
        avg_24h = h.get("last_24_hours", {}).get("avg", 0)
        avg_7d  = h.get("last_7_days", {}).get("avg", 0)
        if avg_7d > 0:
            trends.append((avg_24h - avg_7d) / avg_7d)

    avg_trend = sum(trends) / len(trends) if trends else 0
    max_trend = max(trends) if trends else 0

    return {
        "avg_input_trend_24h": avg_trend,
        "max_input_trend_24h": max_trend,
        "velocity_alert":      max_trend > 0.05,   # +5% en 24h = signal
        "saturated":           avg_trend > 0.10,   # +10% moyen = fenêtre fermée
    }
```

Le flag `velocity_alert` déclenche une alerte : "⚡ Les inputs de ce trade-up montent — fenêtre de profit en cours de fermeture."

---

#### Détection de manipulation de prix (pump groups)

Des groupes coordonnés créent des pumps artificiels sur les skins à faible supply. L'AK-47 Safari Mesh a été multiplié par 20× en quelques semaines. Ces opportunités sont des pièges.

```python
def detect_pump(history: dict, items: dict) -> dict:
    avg_7d   = history["last_7_days"]["avg"]   or 0
    avg_30d  = history["last_30_days"]["avg"]  or 0
    vol_7d   = history["last_7_days"]["volume"]  or 0
    vol_30d  = history["last_30_days"]["volume"] or 0
    quantity = items.get("quantity", 0)

    hausse_7d_30d = (avg_7d - avg_30d) / avg_30d if avg_30d else 0

    pump_score = 0
    if hausse_7d_30d > 0.15:  pump_score += 2  # +15% en 7j
    if quantity < 20:          pump_score += 1  # supply très faible
    if vol_7d > vol_30d * 0.5: pump_score += 1  # volume concentré sur 7j

    return {
        "pump_score":  pump_score,        # 0=normal, 3-4=probable pump
        "pump_alert":  pump_score >= 3,
        "hausse_7d":   hausse_7d_30d,
    }
```

---

#### Scalability score — répétabilité du trade-up

Un trade-up profitable à 1× n'a pas la même valeur qu'un trade-up profitable à 50×.

```python
def calculate_scalability(input_skins: list, skinport_items: dict) -> dict:
    qty_per_run = 10
    min_repeats = float("inf")
    bottleneck  = None

    for skin in input_skins:
        qty = skinport_items.get(skin["id"], {}).get("quantity", 0)
        runs = qty // qty_per_run
        if runs < min_repeats:
            min_repeats = runs
            bottleneck  = skin["name"]

    return {
        "max_repeats":     min_repeats,
        "bottleneck_skin": bottleneck,
        "scalable_10x":    min_repeats >= 10,
        "scalable_50x":    min_repeats >= 50,
    }
```

Affiché : "Répétable 8× | Goulot : AK-47 Redline FT (qty=80)"

---

#### Doppler phases — pondération si output Doppler

Si un trade-up peut produire un couteau Doppler, les phases ont des valeurs très différentes. L'EV doit pondérer par phase, pas utiliser un prix médian générique.

```python
DOPPLER_PHASE_WEIGHTS = {
    "Phase 1": 0.225, "Phase 2": 0.225,
    "Phase 3": 0.225, "Phase 4": 0.225,
    "Ruby": 0.020, "Sapphire": 0.020,
    "Black Pearl": 0.010, "Emerald": 0.050,
}

def get_doppler_ev(output_skin: dict, skinport_items: dict) -> float:
    if "Doppler" not in output_skin.get("name", ""):
        return None
    ev = 0
    for phase, w in DOPPLER_PHASE_WEIGHTS.items():
        data = skinport_items.get(f"{output_skin['name']} ({phase})")
        if data and data.get("median_price"):
            ev += w * data["median_price"]
    return ev or None
```

---

#### Kelly Criterion — position sizing recommandé

Absent de tous les outils concurrents. La communauté recommande le half-Kelly : le full Kelly a 1/3 de probabilité de diviser le bankroll par deux avant de le doubler. Règle absolue : jamais plus de 5% du bankroll sur un seul trade-up.

```python
def kelly_position_size(ev_nette: float, cout_ajuste: float,
                        win_prob: float, bankroll: float) -> dict:
    b = ev_nette / cout_ajuste  # ratio gain/mise
    p, q = win_prob, 1 - win_prob

    if b <= 0 or p <= 0:
        return {"kelly_fraction": 0, "recommended_size": 0, "pct_bankroll": 0}

    f_full  = (b * p - q) / b
    f_half  = f_full / 2
    safe    = min(f_half, 0.05)  # cap à 5% du bankroll

    return {
        "kelly_full":       round(f_full, 4),
        "kelly_half":       round(f_half, 4),
        "recommended_size": round(bankroll * safe, 2),
        "pct_bankroll":     round(safe * 100, 1),
    }
```

---

#### StatTrak liquidity flag

Les trade-ups StatTrak ont un marché structurellement moins liquide. Un output StatTrak illiquide peut rester invendu des semaines même avec une EV positive.

```python
def check_stattrak_liquidity(output_skin: dict, history: dict) -> str:
    is_st  = "StatTrak" in output_skin.get("name", "")
    vol_30d = history.get("last_30_days", {}).get("volume", 0)

    if is_st and vol_30d < 10:  return "stattrak_illiquid"
    if is_st and vol_30d < 30:  return "stattrak_low_liq"
    if is_st:                   return "stattrak_ok"
    return "normal"
```

---

#### Avertissement systémique permanent — risque Valve

Le risque Valve est existentiel et non modélisable. La MAJ octobre 2025 a effacé ~2 Mrd$ en 24h. Kontract.gg affiche un avertissement permanent visible dans le dashboard et dans chaque alerte :

```
⚠️ Risque systémique : toute mise à jour Valve peut invalider les opportunités en cours.
   Les prix peuvent varier de ±30% en quelques heures sans préavis.
```

---

## 5. Stack technique

### 5.1 Composants recommandés

| Composant | Technologie | Version | Justification |
|-----------|------------|---------|--------------|
| Backend / Logique | Python | 3.11+ | NumPy vectorisé pour le scan EV, APScheduler, httpx async |
| Base de données | SQLite → PostgreSQL | 3.45+ / 15+ | SQLite pour MVP (zero config), migration PostgreSQL en V1 |
| Cache prix | Redis | 7+ | TTL 5 min natif, performances lectures élevées |
| Scheduler | APScheduler | 3.10+ | Jobs récurrents Skinport toutes les 5 min, ByMykel 1x/semaine |
| API Backend | FastAPI | 0.100+ | Async natif, documentation Swagger auto, léger |
| Interface MVP | Streamlit | 1.28+ | Dashboard Python pur, zéro frontend, déployable en heures |
| Interface V2 | React + TailwindCSS | 18+ / 3+ | UX professionnelle après validation PMF |
| Auth | Supabase Auth | — | OAuth Steam natif, sessions, gratuit jusqu'à 50k MAU |
| Paiements | Stripe | — | Abonnements récurrents, portail client self-serve |
| Alertes Telegram | python-telegram-bot | 20+ | Librairie officielle Telegram, stable |
| Compression | brotli (Python) | 1.0+ | Obligatoire pour décoder les réponses Skinport /v1/items |
| Déploiement | Railway | — | ~7$/mois, zero DevOps, déploiement GitHub auto |
| Monitoring | Sentry + UptimeRobot | — | Alertes erreurs + downtime, gratuits aux seuils MVP |

### 5.2 Dépendance critique : décompression Brotli

Les endpoints Skinport `/v1/items` et `/v1/sales/history` exigent le header `Accept-Encoding: br`. **C'est obligatoire, pas optionnel.** Sans ce header, la requête échoue.

```bash
# Installation
pip install httpx[brotli] --break-system-packages
```

```python
# Usage — brotli géré automatiquement par httpx
import httpx

async with httpx.AsyncClient() as client:
    r = await client.get(
        "https://api.skinport.com/v1/items",
        params={"app_id": 730, "currency": "EUR"},
        headers={"Accept-Encoding": "br"}  # OBLIGATOIRE
    )
    items = r.json()  # Décompression automatique
```

### 5.3 Structure du projet MVP

```
kontract/
├── data/
│   ├── models.py          # SQLAlchemy : Collection, Skin, Price, Opportunity
│   ├── bymykel.py         # Chargement + MAJ hebdo BDD depuis ByMykel API
│   └── database.py        # Connexion SQLite/PostgreSQL + Redis
├── fetcher/
│   ├── skinport.py        # Client Skinport API async (items + history)
│   └── steam.py           # Client Steam Market API (prix référence)
├── engine/
│   ├── ev_calculator.py   # Formule EV + float crafting
│   └── scanner.py         # Scan vectorisé NumPy, filtres, scoring
├── alerts/
│   ├── telegram_bot.py    # Bot Telegram + commandes /config /pause /resume
│   └── notifier.py        # Match opportunités ↔ profils utilisateurs
├── ui/
│   └── dashboard.py       # Streamlit : tableau opps, filtres, détail
├── auth/
│   └── supabase.py        # OAuth Steam + gestion sessions
└── main.py                # APScheduler + orchestration + startup
```

---

## 6. Roadmap

### 6.1 Phases de développement

| Phase | Durée | Livrables techniques | Sources données | Go-live |
|-------|-------|---------------------|----------------|---------|
| **MVP** | 3 semaines | BDD ByMykel + Skinport fetcher + moteur EV + bot Telegram + Streamlit | ByMykel + Skinport + Steam | Semaine 3 |
| **V1 — Lancement** | 3 semaines | Auth Supabase+Steam, Stripe Free/Trader/Pro, filtres perso, calculateur manuel | Idem MVP | Semaine 6 |
| **V2 — Croissance** | 4 semaines | BUFF163 scraping direct, float crafting dans EV, React dashboard, API Pro | + BUFF163 direct | Semaine 10 |
| **V3 — Expansion** | Continu | Pricempire API si besoin, StatTrak, mobile, ML, Rust/Dota 2 | + Pricempire si MRR > 1 800€ | Semaine 16+ |

> **Conseil démarrage** : Commencer par `bymykel.py` (semaine 1) : télécharger `collections.json` + `skins.json`, construire la BDD SQLite et vérifier que le pool d'outputs est correct sur 5–10 collections manuellement. C'est la fondation de tout le moteur EV.

### 6.2 Plan semaine par semaine

| Semaine | Actions techniques | Actions marketing |
|---------|--------------------|------------------|
| **S1** | Script `bymykel.py` : téléchargement + parsing `collections.json` + `skins.json` → BDD SQLite. Vérification manuelle des pools d'outputs sur 10 collections. Connexion Skinport API : premier fetch `/v1/items`. | Créer compte Reddit r/csgomarketforum. Observer les discussions outils trade-up. Identifier 20 potentiels beta testeurs Discord. |
| **S2** | Agrégateur complet Skinport (items + history) avec cache Redis. Moteur EV en ligne de commande. Tests sur 20 trade-ups réels — vérification cohérence EV calculée vs prix marché. | Contacter 10 beta testeurs Discord. Enregistrer kontract.gg sur Porkbun (~52$/an). Préparer 3 posts éducatifs Reddit. |
| **S3** | Bot Telegram fonctionnel + commandes `/config` `/pause` `/resume`. Dashboard Streamlit. Déploiement Railway. Gestion utilisateurs basique. | Lancement beta privée 10 users. Collecte feedback structuré. Page kontract.gg en ligne. |
| **S4** | Stripe Free/Trader/Pro. Alertes Telegram configurables. Calculateur manuel. Reverse finder (output → inputs optimaux). | Premier post Reddit public. Approcher 3 créateurs contenu CS2 pour affiliation. |
| **S5–S8** | BUFF163 scraping direct, float crafting dans EV, React V2. | Affiliation 20–30%, SEO, Discord CS2 servers, optimisation conversion. |

---

## 7. Risques & mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|------------|--------|-----------|
| ByMykel arrête de maintenir le repo | Faible | Modéré | Parser directement `items_game.txt` via Steam ISteamEconomy en phase 2 (architecture déjà prévue) |
| Skinport modifie ou bloque son API publique | Faible | Élevé | Ajouter Steam Market API comme fallback + scraper Skinport en dernier recours |
| Valve modifie les règles des trade-ups | Modérée | Élevé | Architecture modulaire : seul `ev_calculator.py` est à mettre à jour |
| Rate limit Skinport dépassé (scaling) | Modérée (phase 2) | Faible | Passer sur Pricempire API dès que MRR > 1 800€, ou réduire fréquence refresh |
| Concurrent clône Kontract.gg | Modérée | Modéré | Pool score + liquidité = différenciateurs techniques rapides à utiliser, lents à copier |
| Churn élevé suite à un mois sans opportunités | Modérée | Modéré | Garantie 30j basée sur qualité des signaux, contenu éducatif pour fidéliser |
| Marché CS2 s'effondre (Valve abandonne) | Très faible | Critique | Architecture extensible vers Rust, Dota 2, TF2 en V3 |

---

## Résumé exécutif technique v2.0

La version 2.0 intègre les données de marché réelles collectées en mars 2026. La principale évolution par rapport à la v1.0 est l'**élimination de Pricempire API du MVP** (trop cher : 119.90$/mois / 10 000 appels) et son remplacement par une architecture 100% gratuite basée sur **ByMykel CSGO-API + Skinport API**.

Cette architecture est techniquement supérieure pour le MVP :
- Les données ByMykel fournissent exactement la structure de pool d'outputs nécessaire
- L'endpoint `/v1/sales/history` de Skinport fournit le score de liquidité — le différenciateur clé de Kontract.gg — sans aucun coût
- La seule contrainte technique nouvelle est la décompression Brotli obligatoire pour les endpoints Skinport (`httpx[brotli]` — 1 ligne d'installation)

| Coût données MVP | Délai MVP | Lignes de code | Rate limit Skinport |
|-----------------|-----------|----------------|---------------------|
| **0 €** | 3 semaines | ~1 500 | 8 req/5min |

---

*Kontract.gg — Confidentiel — Mars 2026*
