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
   - 4.1 BDD Collections
   - 4.2 Agrégateur de prix
   - 4.3 Moteur de calcul EV
   - 4.4 Sélection et gestion des inputs (filtres + score hybride)
   - 4.4.2 Suivi du panier — PanierState
   - 4.5 Liquidité des inputs
   - 4.6 Kontract Score v3
   - 4.7 Détections avancées (recipe velocity, pump, scalability, Kelly, Doppler)
   - 4.7.1 Décision d'abandon de panier
   - 4.8 Portfolio Engine + BuyAlertEngine
   - 4.9 Exécution & Détection automatique de l'output
   - 4.10 P&L Tracker
   - 4.11 Interface utilisateur — 4 pages
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

> **Hors scope MVP** : Sync inventaire Steam auto (V1), OutputDetector (V1), CSFloat float auto (V1), P&L Tracker (V1), float-conditional EV (V2), BUFF163 scraping direct (V2), multi-sourcing inputs (V2), Pricempire API (V3 si MRR > 1 800€), app mobile (V3), StatTrak dédié (V3).

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
| Steam Inventory API | Inventaire d'un compte (items + assetids + inspect links) | API publique (inventaire public requis) | 1x/5 min | 0€ | ✓ Autorisé | ~1 req/min recommandé |
| CSFloat API | Float exact d'un item via son lien inspect | API REST publique | À la demande | 0€ | ✓ Autorisé — service tiers | ~100 req/heure |
| Skinport WebSocket `saleFeed` | Listings individuels temps réel (prix, float, stickers, pattern) | WebSocket socket.io + msgpack | Continu | 0€ | ✓ Autorisé — API officielle | Pas de limite documentée |

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

### 3.1 Vue d'ensemble — modules par phase

| Module | Rôle | Technologie | Phase |
|--------|------|-------------|-------|
| 4.1 BDD Collections | Structure statique : collections, raretés, floats, pools (ByMykel) | Python + SQLite → PostgreSQL | MVP S1 |
| 4.2 Agrégateur prix | Prix toutes les 5 min — Skinport REST API | Python + APScheduler + Redis | MVP S2 |
| 4.3 Moteur EV | Calcul EV, filtrage, Kontract Score | Python + NumPy vectorisé | MVP S2–3 |
| 4.4 Sélection inputs | Hard filters + score hybride listing | Python | MVP S3 |
| 4.4.2 PanierState | Suivi des inputs achetés, sync Steam | Python + Steam API | MVP/V1 |
| 4.5 Liquidité inputs | Vérification exécutabilité du panier | Python | MVP S3 |
| 4.6 Kontract Score | Score composite Sharpe ratio | Python | MVP S3 |
| 4.7 Détections avancées | Recipe velocity, pump, scalability, Kelly | Python | MVP S3 |
| 4.8 Portfolio Engine | Gestion multi-paniers, BuyAlertEngine WebSocket | Python + socket.io | MVP/V1 |
| 4.9 Exécution & Output | OutputDetector, snapshot inventaire | Python + Steam API + CSFloat | V1 |
| 4.10 P&L Tracker | Enregistrement résultats, précision EV | Python | V1 |
| 4.11 Interface UI | 4 pages : Scanner / Portefeuille / Calculateur / P&L | Streamlit → React | MVP/V2 |

### 3.2 Flux de données — séquence complète

**Cycle de fond (toutes les 5 min) :**
1. APScheduler → Skinport `/v1/items` + `/v1/sales/history` (2 req/5min, 25% du quota)
2. Normalisation + cache Redis TTL 5min + écriture PostgreSQL si variation > 0.5%
3. Scanner EV vectorisé NumPy sur toutes les combinaisons (~2–5 sec)
4. Filtrage selon profils utilisateurs → opportunités qualifiées stockées en BDD
5. Portfolio Engine : réévaluation des Kontract Scores des paniers actifs
6. Détection d'abandon si score sous seuil → notification Telegram

**Job hebdomadaire :**
7. ByMykel `collections.json` + `skins.json` → rebuild BDD pools d'outputs

**Flux temps réel (WebSocket continu) :**
8. BuyAlertEngine écoute le WebSocket Skinport (`saleFeed`)
9. Pour chaque listing entrant : hard filters + score hybride en < 500ms
10. Si score ≥ 60 et skin nécessaire dans un panier actif → alerte Telegram avec lien direct

**Cycle panier (V1) :**
11. Sync inventaire Steam toutes les 5min → mise à jour PanierState
12. Panier complet → OutputDetector prend un snapshot puis poll toutes les 30s
13. Nouvel item détecté → float via CSFloat API → pré-remplissage `/executed`
14. Confirmation utilisateur → enregistrement P&L + vérification précision float

---

## 4. Spécifications fonctionnelles

### 4.1 Module 1 — Base de données des collections

#### Construction depuis ByMykel

```python
import asyncio, json, sqlite3
import httpx

BASE_URL = "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en"

async def build_collections_db():
    # Stack 100% async httpx - coherent avec le reste du projet
    async with httpx.AsyncClient() as client:
        collections_r = await client.get(f"{BASE_URL}/collections.json")
        skins_r       = await client.get(f"{BASE_URL}/skins.json")

    collections = collections_r.json()
    skins       = skins_r.json()

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

# Appel depuis main.py via APScheduler:
# scheduler.add_job(build_collections_db, "interval", weeks=1)
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

-- Suivi du panier en cours
trade_up_baskets : id, user_id, opportunity_id,
                   n_required,           -- 10 ou 5 (Covert)
                   status,               -- "in_progress" | "ready" | "detected" | "executed" | "abandoned"
                   inventory_snapshot,   -- JSON : état inventaire Steam avant trade-up (OutputDetector)
                   output_detected,      -- market_hash_name de l'output auto-détecté
                   output_float,         -- float de l'output détecté
                   output_wear,          -- FN / MW / FT / WW / BS
                   created_at, updated_at

basket_items     : id, basket_id,
                   market_hash_name,
                   assetid,              -- NULL si déclaré avant d'être dans l'inventaire
                   float_value,
                   float_norm,           -- précalculé
                   price_paid,
                   source,               -- "manual" | "steam_inventory" | "skinport_webhook"
                   acquired_at
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

| Plateforme | Frais acheteur | Frais vendeur | Impact coût inputs | Disponible MVP |
|-----------|---------------|--------------|-------------------|----------------|
| Skinport | **0%** | 3% | Référence | ✓ |
| Steam Market | 0% | 15% | Identique Skinport côté achat | ✓ |
| BUFF163 | 2.5% | 2.5% | +2.5% sur le coût inputs | Phase 2 |

> ⚠️ Sur Skinport et Steam Market, les frais sont intégralement côté vendeur. L'acheteur paie exactement le prix affiché. Sur BUFF163, l'acheteur paie le prix affiché + 2.5%.

L'avantage de BUFF163 est sur le **prix de marché** (15–30% moins cher que Steam), pas sur les frais. Sur un panier à 70€ sur BUFF163 vs 100€ sur Skinport : coût BUFF163 = 71.75€ vs 100€ → économie réelle ~28€ sur ce panier.

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

#### Système de filtrage et score hybride des listings

Pour chaque opportunité, le scanner évalue chaque listing disponible sur Skinport en deux étapes séquentielles : **filtres éliminatoires** (binaires, pas de score) puis **score hybride** (uniquement pour les listings qui passent tous les filtres).

---

##### Étape 1 — Filtres éliminatoires (hard filters)

Un listing qui échoue à l'un de ces filtres est **rejeté immédiatement** — il n'entre pas dans le calcul du score hybride. Ces filtres ne sont pas configurables car ils correspondent à des règles absolues.

```python
def apply_hard_filters(listing: dict, target: dict) -> tuple[bool, str]:
    """
    Retourne (True, None) si le listing passe tous les filtres.
    Retourne (False, "raison") sinon.
    Les filtres sont appliqués dans l'ordre du plus rapide au plus lent.
    """

    # F1 — Souvenir interdit (règle Valve absolue)
    if listing.get("souvenir"):
        return False, "souvenir_interdit"

    # F2 — Cohérence StatTrak avec le panier
    if listing.get("stattrak") != target["stattrak"]:
        return False, "stattrak_incoherent"

    # F3 — Trade lock (Skinport garantit 0j, vérification de sécurité)
    if listing.get("lock_days", 0) > 0:
        return False, f"trade_lock_{listing['lock_days']}j"

    # F4 — Sticker de valeur (ne pas détruire un sticker rare)
    if has_valuable_sticker(listing.get("stickers", [])):
        return False, "sticker_precieux"

    # F5 — Pattern premium (Case Hardened bleu, Fade, etc.)
    if has_premium_pattern(listing["name"], listing.get("pattern")):
        return False, "pattern_premium"

    # F6 — Prix aberrant (anomalie de listage)
    if is_price_anomaly(listing["price"], target["median_price"]):
        return False, "prix_aberrant"

    # F7 — Hors budget maximum configuré par l'utilisateur
    if listing["price"] > target["max_input_price"]:
        return False, "hors_budget"

    # F8 — Float hors plage cible (si float crafting activé)
    if target.get("float_crafting") and listing.get("float_norm") is not None:
        norm = listing["float_norm"]
        if not (target["norm_min"] <= norm <= target["norm_max"]):
            return False, f"float_hors_plage_{norm:.3f}"

    return True, None
```

---

##### Étape 2 — Score hybride (soft score)

Pour les listings qui passent tous les hard filters, un score composite de 0 à 100 est calculé. Plus le score est élevé, plus le listing est optimal à acheter.

```python
def calculate_listing_score(listing: dict, target: dict, panier_state: dict) -> dict:
    """
    Score hybride 0–100 pour un listing qui a passé les hard filters.

    Dimensions :
    - Prix (40%)     : économie vs médiane + économie vs panier actuel
    - Float (35%)    : précision par rapport à la contribution marginale requise
    - Qualité (15%)  : absence de stickers, pattern neutre, homogénéité
    - Disponibilité (10%) : trade lock résiduel, fraîcheur du listing
    """

    # ── DIMENSION PRIX (40%) ──────────────────────────────────────────

    # Économie vs médiane (0 à 1 : plus négatif = meilleur)
    median        = target["median_price"]
    price         = listing["price"]
    price_saving  = (median - price) / median          # positif = en dessous médiane
    price_score   = min(1.0, max(0.0, 0.5 + price_saving * 2))
    # −20% vs médiane → score 0.90 | +10% → score 0.30 | au niveau médiane → 0.50

    # Économie marginale dans le panier (ce listing améliore-t-il le coût moyen ?)
    current_avg   = panier_state.get("avg_price", median)
    marginal_gain = (current_avg - price) / current_avg if current_avg > 0 else 0
    marginal_score = min(1.0, max(0.0, 0.5 + marginal_gain * 3))

    prix_final = 0.65 * price_score + 0.35 * marginal_score

    # ── DIMENSION FLOAT (35%) ─────────────────────────────────────────

    if listing.get("float_norm") is not None and target.get("float_crafting"):
        float_norm     = listing["float_norm"]
        norm_center    = (target["norm_min"] + target["norm_max"]) / 2
        norm_range     = target["norm_max"] - target["norm_min"]

        # Précision par rapport au centre de la plage cible
        distance       = abs(float_norm - norm_center)
        precision      = max(0.0, 1.0 - (distance / (norm_range / 2)))

        # Contribution marginale : est-ce que ce float amène le panier
        # vers l'objectif ou l'en éloigne ?
        required_min, required_max, required_center = \
            required_float_norm_remaining(
                panier_state.get("floats_bought", []),
                target["norm_min"],
                target["norm_max"]
            )
        marginal_float = max(0.0, 1.0 - abs(float_norm - required_center))

        float_final = 0.5 * precision + 0.5 * marginal_float

    else:
        # Pas de float crafting → float neutre, score 0.7 (légèrement positif)
        float_final = 0.7

    # ── DIMENSION QUALITÉ (15%) ───────────────────────────────────────

    # Homogénéité avec les floats déjà achetés
    floats_bought = panier_state.get("floats_bought", [])
    if floats_bought and listing.get("float_norm"):
        avg_bought   = sum(floats_bought) / len(floats_bought)
        homogeneity  = max(0.0, 1.0 - abs(listing["float_norm"] - avg_bought) * 5)
    else:
        homogeneity = 1.0

    # Absence de stickers (même non précieux, préférer listing propre)
    sticker_count  = len(listing.get("stickers", []))
    sticker_score  = 1.0 if sticker_count == 0 else max(0.5, 1.0 - sticker_count * 0.1)

    qualite_final  = 0.6 * homogeneity + 0.4 * sticker_score

    # ── DIMENSION DISPONIBILITÉ (10%) ─────────────────────────────────

    # Fraîcheur du listing (listed récemment = plus de chance d'être encore dispo)
    age_minutes    = listing.get("age_minutes", 60)
    freshness      = max(0.0, 1.0 - age_minutes / 120)  # 0 = 2h+, 1 = instantané

    # Pas de trade lock résiduel (Skinport = 0j normalement)
    lock_score     = 1.0 if listing.get("lock_days", 0) == 0 else 0.5

    dispo_final    = 0.7 * freshness + 0.3 * lock_score

    # ── SCORE FINAL ───────────────────────────────────────────────────

    score = (
        0.40 * prix_final    +
        0.35 * float_final   +
        0.15 * qualite_final +
        0.10 * dispo_final
    ) * 100

    return {
        "score":           round(score, 1),
        "prix_score":      round(prix_final * 100, 1),
        "float_score":     round(float_final * 100, 1),
        "qualite_score":   round(qualite_final * 100, 1),
        "dispo_score":     round(dispo_final * 100, 1),
        "price_saving_pct": round(price_saving * 100, 1),
        "float_norm":      listing.get("float_norm"),
        "recommended":     score >= 60,
        "url":             build_listing_url(listing),
        "inspect_link":    listing.get("link"),
    }
```

---

##### Pipeline complet — de la liste brute aux meilleurs listings

```python
def rank_input_listings(
    raw_listings: list,
    target: dict,
    panier_state: dict,
    top_n: int = 5
) -> dict:
    """
    Pipeline complet : filtre → score → classement.
    Retourne les top_n meilleurs listings + les statistiques de filtrage.
    """
    rejected = []
    candidates = []

    # Étape 1 : filtres éliminatoires
    for listing in raw_listings:
        passed, reason = apply_hard_filters(listing, target)
        if passed:
            candidates.append(listing)
        else:
            rejected.append({"listing": listing, "reason": reason})

    # Étape 2 : score hybride
    scored = []
    for listing in candidates:
        result = calculate_listing_score(listing, target, panier_state)
        scored.append({**listing, **result})

    # Étape 3 : classement par score décroissant
    ranked = sorted(scored, key=lambda x: -x["score"])

    # Statistiques de filtrage
    rejection_summary = {}
    for r in rejected:
        reason = r["reason"].split("_")[0]  # grouper par catégorie
        rejection_summary[reason] = rejection_summary.get(reason, 0) + 1

    return {
        "top_listings":       ranked[:top_n],
        "total_available":    len(raw_listings),
        "passed_filters":     len(candidates),
        "rejected":           len(rejected),
        "rejection_summary":  rejection_summary,
        "best_score":         ranked[0]["score"] if ranked else 0,
        "panier_completable": len(candidates) >= (10 - panier_state.get("n_bought", 0)),
    }
```

---

##### Tableau des pondérations du score hybride

| Dimension | Poids | Critères inclus | Raisonnement |
|-----------|-------|----------------|--------------|
| Prix | 40% | Économie vs médiane + gain marginal panier | Impacte directement l'EV calculée |
| Float | 35% | Précision plage cible + contribution marginale | Détermine la condition de wear de l'output |
| Qualité | 15% | Homogénéité panier + absence stickers | Réduit le risque et la variance |
| Disponibilité | 10% | Fraîcheur du listing + trade lock | Exécutabilité immédiate |

> **Note** : si le float crafting est désactivé (stratégie `cheapest`), la dimension Float passe à 0.7 fixe et le poids restant est redistribué sur le Prix (+15%). Seul le prix et la qualité discriminent alors.

---

##### Exemple de sortie dashboard

```
FAMAS | Rapid Eye Movement MW — 18 listings analysés
✅ Passé les filtres : 14  |  ❌ Rejetés : 4
  Rejetés → sticker_precieux: 1 | prix_aberrant: 2 | float_hors_plage: 1

┌─────────────────────────────────────────────────────────────────┐
│ # │ Score │ Prix  │ Float  │ Prix% │ Float% │ Qualité │ Action  │
├───┼───────┼───────┼────────┼───────┼────────┼─────────┼─────────┤
│ 1 │  84.2 │ 7.93€ │ 0.1430 │  92.0 │   81.0 │    88.0 │ 🛒 BUY  │
│ 2 │  79.5 │ 7.95€ │ 0.1460 │  91.5 │   78.5 │    86.0 │ 🛒 BUY  │
│ 3 │  71.3 │ 8.00€ │ 0.1370 │  88.5 │   72.0 │    90.0 │ ✅ OK   │
│ 4 │  68.9 │ 8.00€ │ 0.1440 │  88.5 │   69.0 │    85.0 │ ✅ OK   │
│ 5 │  51.2 │ 8.47€ │ 0.1460 │  70.0 │   78.5 │    72.0 │ ⚠️ SKIP │
└─────────────────────────────────────────────────────────────────┘

Panier : 0/10 inputs | Budget restant : 100€
Float moyen après achat top-3 : norm ~0.87 → Output prédit : BS
→ Pour viser FT sur l'output, acheter des MW float < 0.09
```

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

### 4.4.2 Module — Suivi du panier en cours (PanierState)

#### Problème

Le score hybride des listings et le calcul du float marginal requis dépendent de ce que l'utilisateur a **déjà acheté**. Sans connaissance de l'état du panier, il est impossible de :
- Calculer le float contribution marginale exacte pour les inputs restants
- Afficher le budget restant
- Prédire la condition de wear finale de l'output
- Alerter l'utilisateur quand le panier est complet et le trade-up exécutable

#### Trois sources de vérité — par ordre de fiabilité

| Source | Fiabilité | Délai | Auth requise | Scope MVP |
|--------|-----------|-------|--------------|-----------|
| Déclaration manuelle | Dépend utilisateur | Immédiat | Non | ✓ |
| Inventaire Steam API | Haute | ~30 sec | Non (inventaire public) | ✓ V1 |
| Transactions Skinport API | Exacte | ~1 min | Oui (API key) | V2 |

---

#### Déclaration manuelle — commandes Telegram

```
/panier add <skin_name> float=<val> prix=<val>
  → Ajoute un input déclaré manuellement

/panier status
  → Affiche l'état du panier + float requis pour les restants

/panier remove <n>
  → Retire l'input n° n du panier

/panier reset
  → Remet le panier à zéro
```

---

#### Synchronisation inventaire Steam (V1)

```python
async def fetch_steam_inventory(steamid: str) -> list:
    """
    Récupère l'inventaire CS2 public d'un compte Steam.
    Aucune auth requise si l'inventaire est public.
    Rate limit : ~1 requête/minute recommandé pour éviter le throttling Steam.
    """
    url = (
        f"https://steamcommunity.com/inventory/{steamid}/730/2"
        f"?l=english&count=5000"
    )
    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=15)
        data = r.json()

    items = []
    descs = {
        f"{d['classid']}_{d['instanceid']}": d
        for d in data.get("descriptions", [])
    }
    for asset in data.get("assets", []):
        key  = f"{asset['classid']}_{asset['instanceid']}"
        desc = descs.get(key, {})
        # Extraire le lien inspect depuis les actions Steam
        inspect_link = next(
            (a["link"].replace("%owner_steamid%", steamid)
                      .replace("%assetid%", asset["assetid"])
             for a in desc.get("actions", [])
             if "inspect" in a.get("name", "").lower()),
            None
        )
        items.append({
            "assetid":          asset["assetid"],
            "market_hash_name": desc.get("market_hash_name"),
            "tradable":         desc.get("tradable", 0) == 1,
            "inspect_link":     inspect_link,
        })
    return items


async def get_float_from_inspect(inspect_link: str) -> float | None:
    """
    Récupère le float d'un item via son lien inspect.
    Utilise l'API publique CSFloat (gratuite, rate limit ~100 req/heure).
    """
    if not inspect_link:
        return None
    url = f"https://api.csfloat.com/?url={inspect_link}"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
    return data.get("iteminfo", {}).get("floatvalue")
```

---

#### Classe PanierState — source de vérité unifiée

```python
class PanierState:
    """
    État du panier en cours pour un trade-up donné.
    Source de vérité unifiée : déclarations manuelles + inventaire Steam.
    Persisté en BDD (table basket_items) et mis à jour à chaque action.
    """

    def __init__(self, opportunity_id: str, user_id: str, n_required: int = 10):
        self.opportunity_id = opportunity_id
        self.user_id        = user_id
        self.n_required     = n_required
        self.inputs_bought  = []
        # [{market_hash_name, float_value, price_paid, source, assetid, acquired_at}]

    # ── Ajout d'un input ──────────────────────────────────────────────

    def add_manual(self, skin_name: str, float_val: float, price: float):
        """Déclaration manuelle via commande Telegram /panier add."""
        self.inputs_bought.append({
            "market_hash_name": skin_name,
            "float_value":      float_val,
            "price_paid":       price,
            "source":           "manual",
            "assetid":          None,
            "acquired_at":      datetime.utcnow(),
        })

    async def sync_from_inventory(self, steamid: str, target_skins: list):
        """
        Synchronise avec l'inventaire Steam.
        Identifie automatiquement les inputs déjà présents dans l'inventaire.
        Appelle CSFloat uniquement pour les items non encore trackés.
        """
        inventory = await fetch_steam_inventory(steamid)
        for item in inventory:
            if item["market_hash_name"] not in target_skins:
                continue
            if self._already_tracked(item["assetid"]):
                continue
            # Récupérer le float via CSFloat
            float_val = await get_float_from_inspect(item["inspect_link"])
            self.inputs_bought.append({
                "market_hash_name": item["market_hash_name"],
                "float_value":      float_val,
                "price_paid":       None,    # prix inconnu via inventaire seul
                "source":           "steam_inventory",
                "assetid":          item["assetid"],
                "acquired_at":      datetime.utcnow(),
            })

    # ── Propriétés calculées ─────────────────────────────────────────

    @property
    def n_bought(self) -> int:
        return len(self.inputs_bought)

    @property
    def n_remaining(self) -> int:
        return self.n_required - self.n_bought

    @property
    def is_complete(self) -> bool:
        return self.n_remaining == 0

    @property
    def floats_bought(self) -> list:
        return [i["float_value"] for i in self.inputs_bought
                if i["float_value"] is not None]

    @property
    def avg_float_norm_current(self) -> float | None:
        return sum(self.floats_bought) / len(self.floats_bought) \
               if self.floats_bought else None

    @property
    def avg_price_bought(self) -> float:
        prices = [i["price_paid"] for i in self.inputs_bought
                  if i["price_paid"] is not None]
        return sum(prices) / len(prices) if prices else 0

    @property
    def total_spent(self) -> float:
        return sum(i["price_paid"] for i in self.inputs_bought
                   if i["price_paid"] is not None)

    def required_float_norm_remaining(
        self,
        target_norm_min: float,
        target_norm_max: float
    ) -> tuple:
        """
        Calcule le float normalisé requis pour les inputs restants
        afin que la moyenne finale reste dans la plage cible.
        Recalculé dynamiquement à chaque ajout d'input.
        """
        if not self.floats_bought:
            return (target_norm_min, target_norm_max,
                    (target_norm_min + target_norm_max) / 2)

        n           = self.n_required
        n_remaining = self.n_remaining
        sum_bought  = sum(self.floats_bought)
        target_ctr  = (target_norm_min + target_norm_max) / 2

        avg_req  = (n * target_ctr - sum_bought) / n_remaining
        avg_min  = (n * target_norm_min - sum_bought) / n_remaining
        avg_max  = (n * target_norm_max - sum_bought) / n_remaining

        return (max(0.0, avg_min), min(1.0, avg_max), avg_req)

    def predict_output_float(self, output_skin: dict) -> float | None:
        """
        Prédit le float de l'output si tous les inputs restants
        ont le float normalisé optimal (centre de la plage cible).
        """
        if not self.floats_bought:
            return None
        # Hypothèse : les restants achètent exactement le float requis
        _, _, req_center = self.required_float_norm_remaining(0.0, 1.0)
        avg_all_norm = (
            sum(self.floats_bought) + req_center * self.n_remaining
        ) / self.n_required
        f_min = output_skin["float_min"]
        f_max = output_skin["float_max"]
        return f_min + avg_all_norm * (f_max - f_min)

    def _already_tracked(self, assetid: str) -> bool:
        return any(i["assetid"] == assetid for i in self.inputs_bought
                   if i["assetid"])
```

---

#### Schéma BDD — tables panier

```sql
-- Panier en cours par opportunité et utilisateur
trade_up_baskets :
    id              UUID PRIMARY KEY,
    user_id         UUID REFERENCES users(id),
    opportunity_id  UUID REFERENCES opportunities(id),
    n_required      INTEGER DEFAULT 10,
    status          TEXT,   -- "in_progress" | "ready" | "executed" | "abandoned"
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP

-- Items du panier (un par input acheté)
basket_items :
    id               UUID PRIMARY KEY,
    basket_id        UUID REFERENCES trade_up_baskets(id),
    market_hash_name TEXT NOT NULL,
    assetid          TEXT,               -- NULL si déclaré avant d'être dans l'inventaire
    float_value      DECIMAL(10, 8),
    float_norm       DECIMAL(10, 8),     -- précalculé
    price_paid       DECIMAL(10, 2),
    source           TEXT,               -- "manual" | "steam_inventory" | "skinport_webhook"
    acquired_at      TIMESTAMP
```

---

#### Notification Telegram — état du panier

À chaque mise à jour du panier, l'utilisateur reçoit un récapitulatif :

```
📦 Panier mis à jour — FAMAS REM → AWP Fever Dream FN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Progression : 3/10 inputs ✓
Dépensé    : 23.81€ | Restant : 76.19€

Inputs confirmés :
  ✓ FAMAS REM MW  0.143  7.93€  (Steam)
  ✓ FAMAS REM MW  0.146  7.95€  (Steam)
  ✓ FAMAS REM MW  0.137  7.93€  (Steam)

Float actuel  : avg_norm = 0.880
Float requis  : norm 0.76–0.89 pour les 7 restants
Output prédit : Field-Tested ✓

→ Prochain listing recommandé (score 84.2) :
  7.93€ | float 0.143 | norm 0.880
  🛒 https://skinport.com/item/famas-rapid-eye-movement/6934215
```

Quand le panier est complet :

```
✅ Panier complet — Trade-up prêt à exécuter !
10/10 inputs dans l'inventaire ✓
Float output prédit : 0.247 → Field-Tested ✓
EV nette estimée    : +14.20€ (+18% ROI)
Kontract Score      : 24.7

→ Exécuter maintenant dans CS2 : Inventaire → Trade Up Contract
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

### 4.7.1 Décision d'abandon de panier

La décision d'abandonner un panier en cours est délicate : on a déjà dépensé de l'argent (inputs achetés), et l'abandon implique de revendre ces inputs avec une perte potentielle. Le principe est de comparer **le coût de l'abandon** (perte certaine maintenant) vs **l'EV si on continue** (gain espéré mais incertain).

```python
def should_abandon_basket(
    basket_state:    "PanierState",
    opportunity:     dict,
    min_score:       float = 5.0,
    prices:          dict  = None
) -> tuple[bool, str]:
    """
    Décide si un panier en cours doit être abandonné.
    Compare le coût de la revente forcée vs l'EV restante.

    Retourne (True, raison) si l'abandon est recommandé.
    """
    current_score = opportunity.get("kontract_score", 0)

    # Cas 1 : score encore au-dessus du seuil → continuer
    if current_score >= min_score:
        return False, "score_ok"

    # Cas 2 : panier vide → abandonner sans frais
    if basket_state.n_bought == 0:
        return True, "score_bas_panier_vide"

    # Cas 3 : calculer le coût réel de l'abandon
    resell_value = 0.0
    if prices:
        for item in basket_state.inputs_bought:
            skin_data   = prices.get(item["market_hash_name"], {})
            market_price = skin_data.get("min_price") or skin_data.get("median_price", 0)
            # Frais vendeur Skinport 3%
            resell_value += market_price * (1 - FEES["skinport"]["seller"])

    total_spent   = basket_state.total_spent
    abandon_loss  = total_spent - resell_value
    ev_remaining  = opportunity.get("ev_nette", 0)

    # Si l'EV restante couvre la perte d'abandon → continuer malgré score bas
    if ev_remaining > abandon_loss:
        return False, (
            f"ev_continue_{ev_remaining:.2f}€ > perte_abandon_{abandon_loss:.2f}€"
        )

    # Sinon → recommander l'abandon
    return True, (
        f"score_{current_score:.1f}_sous_seuil_{min_score} | "
        f"perte_abandon_{abandon_loss:.2f}€ < ev_restante_{ev_remaining:.2f}€"
    )
```

**Exemple** : panier 4/10 inputs achetés à 40€, score tombé de 14 → 6 (en dessous du seuil 8), EV nette recalculée = 2€, valeur de revente des 4 inputs = 36€.
- Perte abandon = 40 − 36 = **4€**
- EV restante = **2€**
- 4€ > 2€ → **abandonner** (la perte certaine est moins grave que le risque de continuer)

L'alerte Telegram envoyée à l'utilisateur :

```
⚠️ Abandon recommandé — FAMAS REM → Fever Dream
Score passé : 14.2 → 6.3 (−56%)
Cause : output en baisse -23% sur 7j

Analyse abandon vs continuation :
  Perte si revente maintenant : −4.20€
  EV si on continue           : +2.10€
  → Recommandation : ABANDONNER (économie nette : 2.10€)

Confirmer : /abandon <basket_id>
Ignorer   : /continue <basket_id>
```

---

### 4.8 Module Portfolio — Gestion du portefeuille de trade-ups

#### Vue d'ensemble

La stratégie portefeuille consiste à gérer **plusieurs trade-ups en parallèle** — jusqu'à N paniers simultanés selon le budget disponible. Le Portfolio Engine est le chef d'orchestre : il sélectionne les opportunités, résout les conflits d'inputs, alerte en temps réel sur les meilleurs listings, et réévalue en continu.

**Ce qui est automatisé à 100% :**
- Sélection et ranking des opportunités
- Détection des conflits d'inputs entre paniers
- Surveillance WebSocket des listings en temps réel
- Filtrage et scoring des listings entrants
- Sync inventaire Steam et mise à jour des paniers
- Réévaluation continue du Kontract Score
- Recommandation d'abandon si score chute
- Alerte "panier prêt" quand tous les inputs sont achetés

**Ce qui reste manuel (1 clic) :**
- L'achat sur Skinport (pas d'API d'achat disponible)
- L'exécution du trade-up dans CS2

---

#### Configuration portefeuille — une seule fois

```python
PORTFOLIO_CONFIG = {
    "bankroll":            500.0,   # budget total €
    "max_pct_bankroll":    0.30,    # jamais > 30% engagé simultanément
    "max_pct_per_tradeup": 0.20,    # max 20% du budget par trade-up
    "max_simultaneous":    5,       # nombre max de paniers actifs
    "min_roi":             0.12,    # ROI minimum 12%
    "min_kontract_score":  8.0,     # seuil Kontract Score
    "float_crafting":      False,   # activé en V2
    "source_achat":        "skinport",
    "source_vente":        "skinport",
}

# Dérivés calculés automatiquement
max_capital_engaged  = PORTFOLIO_CONFIG["bankroll"] * PORTFOLIO_CONFIG["max_pct_bankroll"]
max_per_tradeup      = PORTFOLIO_CONFIG["bankroll"] * PORTFOLIO_CONFIG["max_pct_per_tradeup"]
```

---

#### PortfolioEngine — cycle principal

```python
class PortfolioEngine:
    """
    Moteur de portefeuille — tourne en continu.
    Cycle complet toutes les 5 minutes.
    WebSocket Skinport en temps réel pour les alertes d'achat.
    """

    async def run_cycle(self):
        # 1. Récupérer les prix frais Skinport
        prices, history = await fetch_skinport_prices()

        # 2. Scanner toutes les opportunités qualifiées
        all_opps = await self.scanner.scan_all(prices, history)
        qualified = [
            o for o in all_opps
            if o["roi"] >= self.config["min_roi"]
            and o["kontract_score"] >= self.config["min_kontract_score"]
        ]

        # 3. Résoudre les conflits d'inputs
        portfolio = self.resolve_conflicts(
            sorted(qualified, key=lambda x: -x["kontract_score"])
        )

        # 4. Gérer les paniers existants (réévaluation + abandon)
        await self.manage_active_baskets(portfolio, prices)

        # 5. Ouvrir de nouveaux paniers si slots et budget disponibles
        await self.open_new_baskets(portfolio, prices)

    def resolve_conflicts(self, opportunities: list) -> list:
        """
        Si deux opportunités partagent un input, prioriser la plus haute scorée.
        La seconde est mise en attente (visible en UI mais non active).
        """
        allocated = {}  # skin_name → opportunity_id
        result    = []

        for opp in opportunities:
            conflict = next(
                (s["name"] for s in opp["inputs_required"]
                 if s["name"] in allocated),
                None
            )
            if not conflict:
                for s in opp["inputs_required"]:
                    allocated[s["name"]] = opp["id"]
                opp["portfolio_status"] = "active"
            else:
                opp["portfolio_status"] = "waiting_conflict"
                opp["conflict_with"]    = allocated[conflict]
            result.append(opp)

        return result[:self.config["max_simultaneous"]]

    async def manage_active_baskets(self, portfolio, prices):
        for basket in self.active_baskets:
            # Sync inventaire Steam
            await basket.state.sync_from_inventory(
                steamid=basket.user.steamid,
                target_skins=basket.opportunity["input_skin_names"]
            )
            # Réévaluer avec prix frais
            opp = recalculate_opportunity(basket.opportunity, prices)
            basket.opportunity = opp

            if basket.state.is_complete:
                await notify_basket_ready(basket)
                basket.status = "ready"
                continue

            # Vérifier si abandon recommandé
            should_quit, reason = should_abandon_basket(
                basket.state, opp, self.config["min_kontract_score"]
            )
            if should_quit:
                await notify_abandon_recommendation(basket, reason)

    async def open_new_baskets(self, portfolio, prices):
        capital_engaged = sum(
            b.state.total_spent for b in self.active_baskets
        )
        capital_available = (
            self.config["bankroll"] * self.config["max_pct_bankroll"]
            - capital_engaged
        )

        for opp in portfolio:
            if opp["portfolio_status"] != "active":
                continue
            if len(self.active_baskets) >= self.config["max_simultaneous"]:
                break
            if opp["cout_inputs_estime"] > capital_available:
                continue
            if self._basket_exists(opp["id"]):
                continue

            basket = await create_basket(opp, self.user)
            self.active_baskets.append(basket)
            capital_available -= opp["cout_inputs_estime"]
            await notify_basket_opened(basket)
```

---

#### BuyAlertEngine — alertes temps réel WebSocket

```python
class BuyAlertEngine:
    """
    Écoute le WebSocket Skinport.
    Pour chaque listing, vérifie en < 500ms s'il correspond
    à un input nécessaire dans un panier actif.
    """

    async def on_listing(self, sale: dict):
        skin_name = sale["marketHashName"]
        if skin_name not in self.watched_skins:
            return  # early exit — 99% des listings ignorés

        for basket in self.get_baskets_needing(skin_name):
            passed, reason = apply_hard_filters(sale, basket.target)
            if not passed:
                continue

            score = calculate_listing_score(sale, basket.target, basket.state)
            if score["score"] < 60:
                continue

            urgency = "🔴 URGENT" if score["score"] >= 80 else "🟡 BON"
            url = f"https://skinport.com/item/{sale['url']}/{sale['saleId']}"

            await telegram_bot.send(basket.user_id, (
                f"{urgency} — Input recommandé\n"
                f"Trade-up : {basket.opportunity['name']}\n"
                f"Score listing : {score['score']}/100\n"
                f"\n"
                f"Prix   : {sale['salePrice']/100:.2f}€ "
                f"({score['price_saving_pct']:+.1f}% vs médiane)\n"
                f"Float  : {sale.get('wear', 'N/A'):.4f} ✓\n"
                f"Panier : {basket.state.n_bought}/"
                f"{basket.state.n_required} inputs\n"
                f"\n"
                f"→ 🛒 {url}"
            ))
```

---

### 4.9 Module Exécution & Détection automatique de l'output

#### Mécanique du trade-up dans CS2

Quand le panier est complet, l'utilisateur exécute dans CS2 :
1. Inventaire → onglet **Contrats**
2. Glisser les 10 inputs dans les 10 emplacements
3. Vérifier le float output affiché (doit correspondre à la prédiction Kontract.gg)
4. Cliquer **"Envoyer le contrat"** → output instantané, aucun lock

```
Règles Valve :
  - 10 inputs même tier (5 pour Covert → Couteaux/Gants)
  - Tous StatTrak ou tous non-StatTrak
  - Aucun Souvenir
  - Output instantané dans l'inventaire
```

---

#### Détection automatique de l'output (V1)

Valve n'expose pas d'API pour détecter l'exécution. La stratégie : **comparer l'inventaire Steam avant et après** — le nouvel item qui apparaît est l'output.

```python
class OutputDetector:
    """
    Détecte automatiquement l'output en comparant l'inventaire
    avant et après l'exécution. Tourne dès qu'un panier est "ready".
    """

    def __init__(self, basket: dict, steamid: str):
        self.basket           = basket
        self.steamid          = steamid
        self.snapshot_before  = None
        self.expected_outputs = [
            o["market_hash_name"]
            for o in basket.opportunity["outputs"]
        ]

    async def take_snapshot(self):
        inventory = await fetch_steam_inventory(self.steamid)
        self.snapshot_before = {item["assetid"]: item for item in inventory}

    async def poll_for_output(
        self,
        interval_sec: int = 30,
        timeout_sec:  int = 3600
    ) -> dict | None:
        """Interroge l'inventaire toutes les 30s, timeout 1h."""
        if not self.snapshot_before:
            await self.take_snapshot()

        elapsed = 0
        while elapsed < timeout_sec:
            await asyncio.sleep(interval_sec)
            elapsed += interval_sec
            inventory_after = await fetch_steam_inventory(self.steamid)
            output = self._compare_inventories(inventory_after)
            if output:
                return output
        return None

    def _compare_inventories(self, inventory_after: list) -> dict | None:
        before_ids = set(self.snapshot_before.keys())
        new_items  = [
            item for item in inventory_after
            if item["assetid"] not in before_ids
        ]
        for item in new_items:
            if item["market_hash_name"] in self.expected_outputs:
                return item
        return None
```

---

#### Pipeline post-panier-prêt

```python
async def handle_basket_ready(basket: dict, user: dict):
    # 1. Alerte "panier prêt" + instructions CS2
    await notify_basket_ready(basket)

    # 2. Snapshot inventaire avant trade-up
    detector = OutputDetector(basket, user["steamid"])
    await detector.take_snapshot()
    await db.update_basket(basket["id"], {
        "status":             "ready",
        "inventory_snapshot": detector.snapshot_before,
    })

    # 3. Polling détection output (tourne en background)
    output_item = await detector.poll_for_output()

    if output_item is None:
        await telegram_bot.send(user["id"],
            "⏱️ Trade-up non détecté après 1h.\n"
            f"Si exécuté : /executed {basket['id']} output=<nom> float=<val>"
        )
        return

    # 4. Float via CSFloat API
    float_val = await get_float_from_inspect(output_item["inspect_link"])
    wear      = get_output_wear_from_float(float_val, basket.opportunity["output_skin"])
    full_name = f"{output_item['market_hash_name']} ({wear})"

    # 5. Alerte avec pré-remplissage — 1 seul clic pour confirmer
    await telegram_bot.send(user["id"],
        f"🎯 Output détecté automatiquement !\n"
        f"Item   : {full_name}\n"
        f"Float  : {float_val:.6f} → {wear}\n"
        f"Prédit : {basket.opportunity['predicted_wear']}\n"
        f"\nConfirme pour enregistrer le P&L :\n"
        f"/executed {basket['id']} auto"
    )
    await db.update_basket(basket["id"], {
        "status":          "detected",
        "output_detected": full_name,
        "output_float":    float_val,
        "output_wear":     wear,
    })
```

---

#### Vérification de la précision float

Chaque exécution valide la formule de float crafting. Un écart systématique signale une erreur dans les données `float_min/float_max` de ByMykel.

```python
def verify_float_prediction(predicted: float, actual: float,
                             threshold: float = 0.001) -> dict:
    delta    = abs(actual - predicted)
    accurate = delta <= threshold
    return {
        "delta":    round(delta, 6),
        "accurate": accurate,
        "verdict":  "✓ formule correcte" if accurate
                    else f"⚠️ écart {delta:.6f} — vérifier float_min/max ByMykel",
    }
```

Les résultats sont agrégés dans la page P&L → statistique "Précision float" — si elle dérive sous 95%, c'est un signal d'alerte sur la qualité des données.

---

### 4.10 Module P&L Tracker

#### Enregistrement d'une exécution

Deux modes de déclenchement :
- **Auto** : `/executed <basket_id> auto` après détection automatique
- **Manuel** : `/executed <basket_id> output=<n> float=<val>` si timeout

```python
async def record_execution(basket_id: str, output_name: str = None,
                            float_val: float = None, auto: bool = False):
    basket = await db.get_basket(basket_id)
    opp    = basket.opportunity

    if auto:
        detected    = await db.get_detected_output(basket_id)
        output_name = detected["output_detected"]
        float_val   = detected["output_float"]

    sell_price  = await get_current_sell_price(output_name)
    net_revenue = sell_price * (1 - FEES["skinport"]["seller"])
    total_cost  = basket.state.total_spent
    pnl_euros   = net_revenue - total_cost
    pnl_pct     = pnl_euros / total_cost * 100
    ev_accuracy = pnl_euros / opp["ev_nette"] if opp["ev_nette"] else None
    float_check = verify_float_prediction(opp.get("predicted_float", 0), float_val)

    await db.record_pnl({
        "basket_id":       basket_id,
        "output_received": output_name,
        "output_float":    float_val,
        "output_wear":     get_output_wear_from_float(float_val, opp["output_skin"]),
        "sell_price":      sell_price,
        "total_cost":      total_cost,
        "pnl_euros":       pnl_euros,
        "pnl_pct":         pnl_pct,
        "ev_calculated":   opp["ev_nette"],
        "ev_accuracy":     ev_accuracy,
        "float_predicted": opp.get("predicted_float"),
        "float_delta":     float_check["delta"],
        "float_accurate":  float_check["accurate"],
        "detected_auto":   auto,
        "executed_at":     datetime.utcnow(),
    })

    emoji = "🟢" if pnl_euros > 0 else "🔴"
    await telegram_bot.send(basket.user_id, (
        f"{emoji} Trade-up clôturé {'(auto)' if auto else '(manuel)'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Output  : {output_name}\n"
        f"Float   : {float_val:.6f} — {float_check['verdict']}\n"
        f"Vendu   : {sell_price:.2f}€\n"
        f"Coût    : {total_cost:.2f}€\n"
        f"P&L     : {pnl_euros:+.2f}€ ({pnl_pct:+.1f}%)\n"
        f"EV calc : {opp['ev_nette']:+.2f}€ | Précision : {ev_accuracy*100:.0f}%"
    ))
```

#### Tableau automatisation par phase

| Étape | MVP | V1 | V2 |
|-------|-----|----|----|
| Détection achat Skinport | ✗ | ✗ | ✓ transactions API |
| Item arrivé en inventaire | ✓ sync 5min | ✓ sync 5min | ✓ webhook |
| Panier complet | ✓ auto | ✓ auto | ✓ auto |
| Snapshot avant trade-up | ✗ | ✓ auto | ✓ auto |
| Détection output | ✗ | ✓ polling 30s | ✓ polling 30s |
| Float output (CSFloat) | ✗ | ✓ auto | ✓ auto |
| Pré-remplissage /executed | ✗ | ✓ auto | ✓ auto |
| Enregistrement P&L | Manuel | 1 clic confirm | 1 clic confirm |
| Vérification précision float | ✗ | ✓ auto | ✓ auto |

#### Schéma BDD — P&L enrichi

```sql
pnl_records :
    id               UUID PRIMARY KEY,
    basket_id        UUID REFERENCES trade_up_baskets(id),
    user_id          UUID,
    output_received  TEXT,
    output_float     DECIMAL(10,8),
    output_wear      TEXT,              -- FN / MW / FT / WW / BS
    sell_price       DECIMAL(10,2),
    total_cost       DECIMAL(10,2),
    pnl_euros        DECIMAL(10,2),
    pnl_pct          DECIMAL(6,2),
    ev_calculated    DECIMAL(10,2),
    ev_accuracy      DECIMAL(6,3),     -- 1.0 = EV parfaitement réalisée
    float_predicted  DECIMAL(10,8),    -- float prédit par Kontract.gg
    float_delta      DECIMAL(10,8),    -- |float_réel - float_prédit|
    float_accurate   BOOLEAN,          -- delta <= 0.001
    detected_auto    BOOLEAN,          -- auto ou manuel
    executed_at      TIMESTAMP
```

### 4.10 Interface utilisateur — architecture des pages

L'interface MVP (Streamlit) est organisée en **4 pages** accessibles via une sidebar. Chaque page correspond à une phase du workflow utilisateur.

---

#### Page 1 — Scanner (page d'accueil)

Vue en temps réel de toutes les opportunités qualifiées, triées par Kontract Score décroissant.

```
┌─────────────────────────────────────────────────────────────────────┐
│  🎯 KONTRACT.GG          Scanner  Portfolio  Portefeuille  P&L      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  FILTRES RAPIDES                                                      │
│  ROI min [10%▼]  Budget max [100€▼]  Pool max [5▼]  Score min [5▼]  │
│  [✓] Exclure trending_down  [ ] Exclure haute volatilité             │
│                                                                       │
│  42 opportunités trouvées — Mis à jour il y a 2min                   │
│  ⚠️ Risque Valve : toute MAJ peut invalider les opportunités          │
│                                                                       │
│  Score │ Trade-up                    │ROI  │Pool│Vol/j│Inputs│Action │
│  ──────┼─────────────────────────────┼─────┼────┼─────┼──────┼────── │
│  24.7  │ FAMAS REM → Fever Dream FN  │+18% │ 2  │ 38  │🟢 x40│ [+]  │
│  21.3  │ AK Redline → Asiimov FT     │+22% │ 3  │ 95  │🟢 x80│ [+]  │
│  18.9  │ M4A4 Howl in → Dragon       │+15% │ 2  │ 12  │🟡 x8 │ [+]  │
│  ⚡16.2 │ USP Cortex → Black Tie      │+24% │ 4  │ 44  │🟢 x55│ [+]  │
│  ...   │ ...                          │ ... │... │ ... │ ...  │ ... │
│                                                                       │
│  [▼ Voir détail] sur clic de ligne — décomposition complète          │
└─────────────────────────────────────────────────────────────────────┘
```

**⚡ = recipe velocity alert** (inputs en hausse rapide)

Clic sur une ligne → panneau de détail latéral :
- Décomposition EV par outcome avec probabilités
- Floor ratio, win_prob, CV pondéré
- Listings recommandés pour les inputs (top 3 avec score)
- Lien direct vers chaque listing Skinport
- Bouton "Ajouter au portefeuille"

---

#### Page 2 — Portefeuille (gestion des paniers actifs)

Vue en temps réel de tous les paniers en cours pour l'utilisateur.

```
┌─────────────────────────────────────────────────────────────────────┐
│  📦 PORTEFEUILLE          Scanner  Portfolio  Portefeuille  P&L      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Budget : 423€ / 1000€ engagé (42%)  ████████░░░░░░░░░░░░░          │
│  Slots  : 4 / 5 actifs                                               │
│                                                                       │
│  Score  │ Trade-up              │Panier │Budget│Statut   │Action     │
│  ───────┼───────────────────────┼───────┼──────┼─────────┼─────────  │
│  24.7   │ FAMAS → Fever Dream   │ 3/10  │ 24€  │🔄 achat │[Détail]  │
│  21.3   │ AK → Asiimov FT       │ 7/10  │ 62€  │🔄 achat │[Détail]  │
│  18.9   │ M4A4 → Dragon         │10/10  │ 98€  │✅ PRÊT  │[Exécuter]│
│  ⚠️8.3  │ Glock → Bullet        │ 4/10  │ 38€  │⚠️ ↓score│[Abandon] │
│                                                                       │
│  ⚠️ Glock → Bullet : score passé 14.2 → 8.3 (-42%)                  │
│     Perte abandon estimée : 4.20€ | EV restante : 2.80€             │
│     → Recommandation : ABANDONNER                                    │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

Clic sur "Détail" d'un panier → vue complète :
- Liste des inputs déjà achetés (float, prix, source)
- Float normalisé actuel + plage requise pour les restants
- Top 3 listings recommandés en temps réel (WebSocket)
- Prédiction du float output et condition de wear
- Bouton "Sync inventaire Steam"

Clic sur "✅ PRÊT" → instructions pour exécuter dans CS2 + bouton `/executed`

---

#### Page 3 — Calculateur manuel

Outil libre pour calculer l'EV d'une combinaison personnalisée.

```
┌─────────────────────────────────────────────────────────────────────┐
│  🔢 CALCULATEUR           Scanner  Portfolio  Portefeuille  P&L      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  MODE : [Standard ▼]  [Float crafting]  [Reverse (output → inputs)] │
│                                                                       │
│  INPUTS (10 skins)                                                    │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │ Skin 1 : [FAMAS Rapid Eye Movement ▼]  Float : [0.143]  │        │
│  │ Skin 2 : [FAMAS Rapid Eye Movement ▼]  Float : [0.146]  │        │
│  │ ...                                                       │        │
│  └──────────────────────────────────────────────────────────┘        │
│                                                                       │
│  Source achat : [Skinport ▼]   Source vente : [Skinport ▼]           │
│                                                                       │
│  [CALCULER]                                                           │
│                                                                       │
│  RÉSULTATS                                                            │
│  EV nette : +14.20€  ROI : +18%  Kontract Score : 24.7              │
│  Float output prédit : 0.247 → Field-Tested                          │
│  Win prob : 85%  Floor ratio : 42%                                    │
│                                                                       │
│  Outcomes possibles :                                                 │
│  AWP Fever Dream FN   12% │ 42.00€ │ prob win ✓                      │
│  AWP Fever Dream MW   88% │ 18.00€ │ prob win ✓                      │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

#### Page 4 — P&L & Statistiques

Tableau de bord de performance long terme.

```
┌─────────────────────────────────────────────────────────────────────┐
│  📊 P&L & STATS           Scanner  Portfolio  Portefeuille  P&L      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  RÉSUMÉ                        30 derniers jours                     │
│  ┌──────────┬──────────┬──────────┬──────────┐                       │
│  │ +142.30€ │  78%     │ +16.2%   │  94%     │                       │
│  │ P&L net  │ Win rate │ ROI moy  │ Préc. EV │                       │
│  └──────────┴──────────┴──────────┴──────────┘                       │
│                                                                       │
│  COURBE P&L CUMULÉ ───────────────────────────────────────────       │
│  200│                                          ╭──                   │
│  100│                           ╭──────────────╯                     │
│    0│──────────────╭────────────╯                                     │
│     Sem1         Sem2          Sem3           Sem4                    │
│                                                                       │
│  HISTORIQUE DES TRADES                                                │
│  Date  │ Trade-up              │ Output   │ P&L    │ ROI  │ EV prec  │
│  ──────┼───────────────────────┼──────────┼────────┼──────┼───────── │
│  18/03 │ FAMAS → Fever Dream   │ FT 0.247 │+14.20€ │+18%  │ 97%     │
│  15/03 │ AK → Asiimov          │ FT 0.285 │+22.10€ │+25%  │ 108%    │
│  12/03 │ USP → Black Tie       │ BS 0.621 │ -3.40€ │ -4%  │ n/a     │
│  ...                                                                  │
│                                                                       │
│  PRÉCISION EV                                                         │
│  Moyenne : 94% | Min : 71% | Max : 124%                              │
│  → Distribution centrée sur 100% = modèle bien calibré               │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

#### Navigation et scope par phase

| Page | MVP (Streamlit) | V1 | V2 (React) |
|------|----------------|-----|------------|
| Scanner | ✓ Complet | ✓ + filtres perso | ✓ UX améliorée |
| Portefeuille | ✓ Basique (sync manuel) | ✓ + sync Steam auto | ✓ WebSocket temps réel |
| Calculateur | ✓ Complet | ✓ + float crafting | ✓ |
| P&L & Stats | ✗ (phase V1) | ✓ Table simple | ✓ Graphiques interactifs |

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
| WebSocket client | python-socketio | 5+ | Client WebSocket Skinport `saleFeed` (transport socket.io) |
| WebSocket parser | msgpack / socketio-msgpack | — | Parser custom obligatoire pour le WebSocket Skinport |
| Float API | httpx → api.csfloat.com | — | Récupération float exact via liens inspect Steam (V1) |
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
│   ├── models.py            # SQLAlchemy : Collection, Skin, Price, Opportunity,
│   │                        #   Basket, BasketItem, PnlRecord
│   ├── bymykel.py           # Chargement + MAJ hebdo BDD depuis ByMykel API
│   └── database.py          # Connexion SQLite/PostgreSQL + Redis
├── fetcher/
│   ├── skinport_rest.py     # Client Skinport REST API async (items + history)
│   ├── skinport_ws.py       # Client WebSocket Skinport (saleFeed, socket.io + msgpack)
│   ├── steam.py             # Inventaire Steam + Steam Market API
│   └── csfloat.py           # Récupération float via CSFloat API (inspect links)
├── engine/
│   ├── ev_calculator.py     # Formule EV post-oct 2025 + float-conditional EV
│   ├── scanner.py           # Scan vectorisé NumPy, filtres, scoring
│   ├── kontract_score.py    # Kontract Score v3 (Sharpe ratio, floor, hold discount)
│   └── filters.py           # Hard filters + score hybride listings (inputs)
├── basket/
│   ├── panier_state.py      # Classe PanierState — suivi panier en cours
│   ├── output_detector.py   # OutputDetector — snapshot + polling inventaire
│   └── abandon.py           # should_abandon_basket() — logique d'abandon
├── portfolio/
│   ├── portfolio_engine.py  # PortfolioEngine — cycle 5min, conflits, slots
│   └── buy_alert_engine.py  # BuyAlertEngine — WebSocket → alertes < 500ms
├── pnl/
│   └── tracker.py           # record_execution(), verify_float_prediction()
├── alerts/
│   ├── telegram_bot.py      # Bot Telegram + commandes /config /panier /executed
│   └── notifier.py          # Match opportunités ↔ profils utilisateurs
├── ui/
│   ├── pages/
│   │   ├── scanner.py       # Page 1 — Scanner + filtres + détail opportunité
│   │   ├── portefeuille.py  # Page 2 — Paniers actifs + listings recommandés
│   │   ├── calculateur.py   # Page 3 — Calculateur manuel + float crafting
│   │   └── pnl.py           # Page 4 — Historique trades + stats + courbe P&L
│   └── dashboard.py         # Streamlit app root + sidebar navigation
├── auth/
│   └── supabase.py          # OAuth Steam + gestion sessions
└── main.py                  # APScheduler + WebSocket + orchestration + startup
```

---

## 6. Roadmap

### 6.1 Phases de développement

| Phase | Durée | Livrables techniques | Sources données | Go-live |
|-------|-------|---------------------|----------------|---------|
| **MVP** | 3 semaines | BDD ByMykel + Skinport REST fetcher + moteur EV + Kontract Score + hard filters + score hybride listings + bot Telegram + Streamlit 4 pages (Scanner, Portefeuille basique, Calculateur) + PanierState déclaration manuelle + Portfolio Engine (sélection top 10, conflits, alertes WebSocket) | ByMykel + Skinport + Steam | Semaine 3 |
| **V1 — Lancement** | 3 semaines | Auth Supabase+Steam + OAuth Steam, Stripe Free/Trader/Pro, sync inventaire Steam automatique, OutputDetector + polling, CSFloat float auto, P&L Tracker + page P&L, should_abandon_basket() opérationnel, vérification précision float | + Steam Inventory API + CSFloat | Semaine 6 |
| **V2 — Croissance** | 4 semaines | Float-conditional EV, BUFF163 scraping direct, React dashboard, Kelly Criterion UI, multi-sourcing inputs, Pricempire si MRR > 1 800€ | + BUFF163 direct | Semaine 10 |
| **V3 — Expansion** | Continu | StatTrak dédié, mobile, ML prédiction prix, Rust/Dota 2 | + Pricempire si besoin | Semaine 16+ |

> **Conseil démarrage** : Commencer par `bymykel.py` (semaine 1) : télécharger `collections.json` + `skins.json`, construire la BDD SQLite et vérifier que le pool d'outputs est correct sur 5–10 collections manuellement. C'est la fondation de tout le moteur EV.

### 6.2 Plan semaine par semaine

| Semaine | Actions techniques | Actions marketing |
|---------|--------------------|------------------|
| **S1** | Script `bymykel.py` : téléchargement + parsing `collections.json` + `skins.json` → BDD SQLite. Vérification manuelle des pools d'outputs sur 10 collections. Connexion Skinport API : premier fetch `/v1/items`. | Créer compte Reddit r/csgomarketforum. Observer les discussions outils trade-up. Identifier 20 potentiels beta testeurs Discord. |
| **S2** | Agrégateur complet Skinport (items + history) avec cache Redis. Moteur EV en ligne de commande. Tests sur 20 trade-ups réels — vérification cohérence EV calculée vs prix marché. | Contacter 10 beta testeurs Discord. Enregistrer kontract.gg sur Porkbun (~52$/an). Préparer 3 posts éducatifs Reddit. |
| **S3** | Bot Telegram fonctionnel + commandes `/config` `/pause` `/resume`. Dashboard Streamlit. Déploiement Railway. Gestion utilisateurs basique. | Lancement beta privée 10 users. Collecte feedback structuré. Page kontract.gg en ligne. |
| **S4** | Stripe Free/Trader/Pro. Alertes Telegram configurables. Calculateur manuel. Reverse finder (output → inputs optimaux). | Premier post Reddit public. Approcher 3 créateurs contenu CS2 pour affiliation. |
| **S5–S6** | Sync inventaire Steam + OAuth V1. OutputDetector + CSFloat. P&L Tracker. Page P&L Streamlit. should_abandon_basket() activé. | Premiers témoignages utilisateurs. Mise en avant P&L comme preuve sociale. |
| **S7–S8** | Float crafting V2 (float-conditional EV). BUFF163 scraping. Kelly Criterion dans l'UI. | Affiliation 20–30%, SEO, Discord CS2 servers, optimisation conversion. |

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
| CSFloat rate limit saturé (100 req/h) | Modérée (V1+) | Modéré | Ne récupérer le float que sur les items non encore trackés (cache assetid → float). En V2 : parser directement le lien inspect sans API tierce. |
| Inventaire Steam privé (sync impossible) | Modérée | Modéré | Détecter dès l'OAuth Steam si l'inventaire est public. Afficher une instruction "Rends ton inventaire public pour activer la sync automatique". Fallback : déclaration manuelle toujours disponible. |
| WebSocket Skinport multi-tenant | Faible (scaling) | Modéré | Une seule connexion WebSocket Skinport partagée côté serveur, fan-out en interne vers tous les paniers actifs de tous les utilisateurs. Pas de connexion WebSocket par utilisateur. |

---

## Résumé exécutif technique v2.0

La version 2.0 (mars 2026) est une spécification complète couvrant l'ensemble du cycle de vie d'un trade-up CS2 : détection d'opportunités, sélection des meilleurs listings, gestion du portefeuille multi-paniers, exécution automatisée et tracking P&L.

**Architecture clé :**
- 100% gratuit pour le MVP : ByMykel CSGO-API + Skinport API + Steam API
- WebSocket Skinport en temps réel pour les alertes d'achat (< 500ms)
- Kontract Score v3 (Sharpe ratio — suppression du double-comptage win_prob × EV)
- 8 hard filters + score hybride 4 dimensions pour chaque listing
- PanierState avec sync inventaire Steam et calcul dynamique du float marginal requis
- OutputDetector : détection automatique de l'output via comparaison d'inventaire
- P&L Tracker avec vérification de la précision de la formule de float

| Coût données MVP | Délai MVP | Modules | Rate limit Skinport | Dépendances critiques |
|-----------------|-----------|---------|---------------------|-----------------------|
| **0€** | 3 semaines | 11 | 8 req/5min | httpx[brotli], python-socketio, msgpack |

---

*Kontract.gg — Confidentiel — Mars 2026*
