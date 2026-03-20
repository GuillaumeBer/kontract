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
   - 4.1   Module 1  — BDD Collections (ByMykel)
   - 4.2   Module 2  — Agrégateur de prix (Skinport REST + WebSocket)
   - 4.3   Module 3  — Moteur EV (formule post-oct 2025, float-conditional, hold discount)
   - 4.4   Module 4  — Sélection inputs : hard filters + score hybride listings
   - 4.4.2 Module 4b — Suivi du panier (PanierState + sync Steam inventaire)
   - 4.5   Module 5  — Liquidité des inputs
   - 4.6   Module 6  — Kontract Score v4 (Sharpe ratio + momentum multiplier)
   - 4.7   Module 7  — Détections avancées (recipe velocity, pump, scalability, Kelly, Doppler, StatTrak)
   - 4.7.1            Décision d'abandon de panier (should_abandon_basket)
   - 4.7.2            PriceSignalEngine — 9 signaux faibles + momentum score
   - 4.8   Module 8  — Portfolio Engine + BuyAlertEngine (WebSocket temps réel)
   - 4.9   Module 9  — Exécution CS2 & Détection automatique de l'output (OutputDetector)
   - 4.10  Module 10 — P&L Tracker (enregistrement, précision EV, float accuracy)
   - 4.11  Module 11 — OutputSellEngine (décision hold/sell, stop-loss, vélocité capital)
   - 4.13  Module 13 — ActionRecommender (plan d'actions : items exacts + liens directs)
   - 4.14             Interface utilisateur — 5 pages (Plan, Scanner, Portefeuille, Calculateur, P&L)
   - 4.15             Fonctions utilitaires — 16 helpers (calculate_ev, notify_*, etc.)
   - 4.16             Stratégies avancées (reverse finder, Covert, StatTrak, liquidity decay, backtesting)
   - 4.17             Module LLM — 5 LLM calls (patch analyzer, explainer, signals, onboarding, briefing)
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
| 4.11 ActionRecommender | Plan d'actions complet — items exacts + liens directs buy/sell | Python | MVP/V1 |
| 4.12 Interface UI | 5 pages : Plan d'action (accueil) / Scanner / Portefeuille / Calculateur / P&L | Streamlit → React | MVP/V2 |

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
               min_kontract_score,
               -- Configuration slots (calculés via compute_optimal_slots)
               bankroll,            -- capital total déclaré par l'utilisateur
               max_simultaneous,    -- plafond humain de slots (défaut 5)
               slots_optimal,       -- calculé automatiquement
               capital_par_slot,    -- calculé automatiquement
               active

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
               -- Momentum / PriceSignalEngine (v4)
               output_momentum_score,  -- score −0.5 à +1.0 (PriceSignalEngine)
               output_momentum_verdict,-- strong_up | moderate_up | neutral | cautious
               collection_inactive,    -- booléen : collection hors pool de drop
               trend_7d_30d,           -- (avg_7j - avg_30j) / avg_30j de l'output
               pump_candidate,         -- booléen : score pump > 17 + conditions
               seasonal_phase,         -- label saisonnalité (steam_summer_sale, etc.)
               vol_acceleration,       -- vol_7j / (vol_30j/4.3) - 1
               momentum_multiplier,    -- facteur 0.75–1.30 appliqué au score
               kontract_score,         -- score composite final (v4)
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

### 4.4 Module 4 — Sélection et gestion des inputs

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

### 4.5 Module 5 — Liquidité des inputs

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

### 4.6 Module 6 — Kontract Score v4

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
    Kontract Score v4 — intègre:
    - Sharpe ratio (EV/CV) au lieu du double-comptage win_prob × EV
    - Liquidité inputs/outputs pondérée par probabilité
    - Discount trade hold 7j
    - Pénalité haute volatilité
    - Floor ratio (pire outcome / coût)
    - Recipe velocity detection (inputs en hausse = fenêtre qui se ferme)
    - Momentum score output (PriceSignalEngine — collection inactive,
      tendance prix, accélération volume, saisonnalité, pump pattern)
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
    output_momentum        = opportunity.get("output_momentum_score", 0.0) # PriceSignalEngine

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

    # ── Momentum multiplier — PriceSignalEngine (output signals) ───────
    # Convertit le momentum_score (−0.5 à +1.0) en multiplicateur (0.75 à 1.30)
    # Score neutre (0.0) → multiplier 1.00 (aucun effet)
    # Fort signal haussier (+0.55) → multiplier 1.30 (+30%)
    # Conditions défavorables (−0.30) → multiplier 0.85 (−15%)
    if output_momentum >= 0:
        momentum_mult = min(1.30, 1.0 + output_momentum * 0.545)
    else:
        momentum_mult = max(0.75, 1.0 + output_momentum * 0.500)

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
        * momentum_mult          # ← nouveau : amplificateur/atténuateur marché
    )

    return round(kontract_score, 2), {
        "win_prob":          round(win_prob, 3),         # affiché dans l'UI
        "floor_ratio":       round(floor_ratio, 3),      # affiché dans l'UI
        "cv_pond":           round(cv_pond, 3),
        "hold_days":         hold_days,
        "velocity_alert":    input_price_trend > 0.10,
        "momentum_score":    round(output_momentum, 3),  # affiché dans l'UI
        "momentum_mult":     round(momentum_mult, 3),
    }
```

---

#### Exemples chiffrés

**Opportunité A — Solide, exécutable, contexte favorable**
ROI 18%, inputs liquides (qty=40, vol_24h=8), output 40 ventes/7j, pool 3 équilibré
Collection inactive depuis 18 mois, tendance prix 7j/30j = +8%, Steam Summer Sale actif

```
ev_nette=9€, cv_pond=1.4, vol_24h_min=8, floor_ratio=0.42
score_risque  = 9 / √1.4 = 7.61
floor_factor  = 1.00  (floor_ratio >= 0.20)
bonus_out     = ln(1 + (0.33×40+0.33×35+0.33×38)/7) = ln(6.38) = 1.85
hold_discount = 1 - 0.005×7 = 0.965
input_exec    = 1.00  (liquid)
speed_bonus   = ln(1 + 8) = 2.20
velocity_pen  = 1.00  (inputs stables)
volatility    = 1.00

-- Momentum v4 --
momentum_score = 0.25 (inactive) + 0.10 (trend +8%) + 0.07 (vol accél +30%)
               + 0.15 (Steam Summer Sale) = 0.57
momentum_mult  = min(1.30, 1.0 + 0.57 × 0.545) = 1.31 → cappé à 1.30

kontract_score = 7.61 × 1.00 × (1+1.85) × 0.965 × 1.00 × (1+0.15×2.20)
               × 1.00 × 1.00 × 1.30
             = 7.61 × 2.85 × 0.965 × 1.33 × 1.30
             = 36.4
```

**Opportunité A — même opportunité, contexte neutre (hors Steam Sale, collection active)**
```
Même paramètres mais momentum_score = 0.00 → momentum_mult = 1.00
kontract_score = 7.61 × 2.85 × 0.965 × 1.33 × 1.00 = 28.0
```

L'impact du contexte marché : **28.0 → 36.4 (+30%)** grâce au signal saisonnier et à la collection inactive. L'opportunité est la même, mais le moment d'entrée est beaucoup plus favorable.

**Opportunité B — ROI élevé mais risquée + contexte défavorable**
ROI 35%, inputs scarces, output peu liquide, collection active, rentrée scolaire septembre

```
ev_nette=18€, cv_pond=8.5, floor_ratio=0.08
score_risque  = 18 / √8.5 = 6.18
floor_factor  = 0.5 + 0.08×2.5 = 0.70  (floor trop bas)
bonus_out     = ln(1 + 0.19) = 0.17
hold_discount = 0.965
input_exec    = 0.40  (scarce)
speed_bonus   = ln(1 + 0.3) = 0.26

-- Momentum v4 --
momentum_score = 0.00 (collection active) + 0.00 (trend plat)
               + 0.00 (volume normal) - 0.08 (back_to_school) = -0.08
momentum_mult  = max(0.75, 1.0 + (-0.08)×0.500) = 0.96

kontract_score = 6.18 × 0.70 × (1+0.17) × 0.965 × 0.40 × (1+0.15×0.26)
               × 1.00 × 1.00 × 0.96
             = 1.85
```

Malgré un ROI deux fois supérieur, l'opportunité B obtient un Kontract Score **20× plus bas** que A. La pénalité combinée du floor ratio trop bas, des inputs peu liquides, et du contexte saisonnier défavorable reflète correctement le risque réel.

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
| 13 | Contexte marché ignoré | Recherche communautaire mars 2026 | Absent | `PriceSignalEngine` → `momentum_multiplier` 0.75–1.30 dans le Kontract Score |
| 14 | Collection inactive non valorisée | Recherche communautaire | Absent | Signal S1 : +0.25 sur momentum_score |
| 15 | Saisonnalité absente | Recherche communautaire | Absent | Calendrier 12 mois intégré dans PriceSignalEngine |
| 16 | Pump candidat output non détecté | Key-Drop research 2026 | Absent | Score pump `log(price)/log(supply_fn) > 17` |
| 17 | Corrélation inter-skins absente | Recherche académique 2025 | Absent | Signal S6 : tendance collection voisine |

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
🎯 Kontract Score : 36.4  (+30% vs neutre)
AK-47 Redline FT → AWP Fever Dream FN
ROI : +18% | EV nette : +9.20€ | win_prob : 85% | floor : 42%
Pool : 3 outcomes | Inputs : 🟢 liquid (qty=40) | Kelly : 2.3% du bankroll
Output liquidité : 40 ventes/7j | Prix : 🟢 stable | Répétable 8×
📈📈 Momentum : +57% — collection inactive + tendance +8% + Steam Summer Sale
```

---

### 4.7 Module 7 — Détections avancées et métriques complémentaires

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


### 4.7.2 Module — PriceSignalEngine (signaux faibles de marché)

#### Contexte et justification

La recherche communautaire et académique (mars 2026) identifie des signaux mesurables qui précèdent les mouvements de prix sur les skins CS2. Une thèse de 2025 portant sur 640 145 observations journalières confirme que les features de prix relatifs (moyennes mobiles, écarts), de supply, de statut collection et d'événements calendaires sont les prédicteurs les plus efficaces — avec des modèles XGBoost atteignant un R² ~0.50 sur 7 jours. Ces signaux sont intégrés en deux niveaux : règles déterministes (MVP/V1) et modèle ML (V3).

**Ce que le PriceSignalEngine apporte vs les détections existantes :**

| Détection existante | Scope | PriceSignalEngine |
|---------------------|-------|-------------------|
| `detect_recipe_velocity` | Inputs en hausse (opportunité se referme) | Outputs en hausse (opportunité s'améliore) |
| `detect_pump` | Manipulation coordonnée sur outputs | Momentum organique multi-signaux |
| `high_volatility` flag | Variation 24h brutale | Tendance structurelle 7j/30j/90j |

---

#### Les 9 signaux identifiés — classés par fiabilité

| # | Signal | Type | Fiabilité | Source |
|---|--------|------|-----------|--------|
| S1 | Collection inactive (plus dans le pool de drop) | Structurel long terme | ⭐⭐⭐⭐⭐ | Valve drop pool |
| S2 | Tendance prix 7j/30j positive | Momentum court terme | ⭐⭐⭐⭐ | Skinport history |
| S3 | Accélération du volume (hype naissante) | Momentum précoce | ⭐⭐⭐ | Skinport history |
| S4 | Pump score > 17 (supply limitée + prix bas) | Manipulation détectable | ⭐⭐⭐ | Skinport items |
| S5 | Saisonnalité calendaire (Steam Sales, Majors) | Cyclique prévisible | ⭐⭐⭐ | Calendrier |
| S6 | Corrélation inter-skins (hausse collection voisine) | Propagation | ⭐⭐ | Historique cross |
| S7 | Divergence cross-plateforme (gap Skinport/BUFF163) | Anomalie d'arbitrage | ⭐⭐ | Multi-platform |
| S8 | Méta arme (buff/nerf dans patch notes) | Événementiel | ⭐⭐ | Patch notes |
| S9 | Usage pro/streamer | Événementiel imprévisible | ⭐ | Social monitoring |

**Signal non modélisable :** le risque Valve (MAJ changeant les règles de trade-up) n'a produit aucun signal précurseur avant octobre 2025. L'avertissement systémique permanent reste la seule réponse possible.

---

#### PriceSignalEngine — implémentation

```python
from math import log, sqrt
from datetime import date
from enum import Enum

class MomentumVerdict(str, Enum):
    STRONG_UP   = "strong_up"    # score > 0.55 — conditions très favorables
    MODERATE_UP = "moderate_up"  # score > 0.30
    NEUTRAL     = "neutral"      # score 0.10–0.30
    CAUTIOUS    = "cautious"     # score < 0.10 — conditions défavorables

class PriceSignalEngine:
    """
    Analyse les signaux faibles pour chaque output d'une opportunité.
    Produit un momentum_score de 0 à 1 intégré dans le Kontract Score.

    Sources MVP : Skinport /v1/sales/history + ByMykel collections (active/inactive)
    Sources V2+ : BUFF163 (cross-platform ratio) + patch notes Valve
    """

    # Calendrier saisonnier CS2 documenté
    SEASONAL_CALENDAR = {
        1:  ("post_winter_neutral",  0.00),
        2:  ("neutral",              0.00),
        3:  ("spring_recovery",     +0.05),  # Majors de printemps
        4:  ("major_season",        +0.10),  # ESL / IEM Spring
        5:  ("pre_summer",           0.00),
        6:  ("steam_summer_sale",   +0.15),  # Hausse demande documentée
        7:  ("post_summer_dip",     -0.05),  # Léger dip post-sale
        8:  ("neutral",              0.00),
        9:  ("back_to_school_dip",  -0.08),  # Baisse activité documentée
        10: ("major_season",        +0.10),  # Majors d'automne
        11: ("pre_winter",          +0.05),
        12: ("steam_winter_sale",   +0.15),  # Hausse demande documentée
    }

    def compute_output_momentum(
        self,
        output_skin:  dict,   # données ByMykel (float_min, float_max, collection_id...)
        collection:   dict,   # données ByMykel (active, release_date...)
        history:      dict,   # Skinport /v1/sales/history pour cet output
        items:        dict,   # Skinport /v1/items pour cet output
        peer_skins:   list,   # autres skins de la même collection (corrélation)
    ) -> dict:
        """
        Calcule le momentum score de l'output (0 = neutre, 1 = fort signal haussier).
        Un score négatif est possible si plusieurs signaux baissiers se cumulent.
        """
        signals = {}
        score   = 0.0

        avg_7d  = history.get("last_7_days",  {}).get("avg",    0) or 0
        avg_30d = history.get("last_30_days", {}).get("avg",    0) or 0
        avg_90d = history.get("last_90_days", {}).get("avg",    0) or 0
        vol_7d  = history.get("last_7_days",  {}).get("volume", 0) or 0
        vol_30d = history.get("last_30_days", {}).get("volume", 0) or 0
        supply  = items.get("quantity", 0)
        price   = items.get("min_price") or avg_7d or 0

        # ── S1 : Collection inactive → biais haussier structurel ─────────
        # Les skins hors du pool de drop actif voient leur supply stagner
        # tandis que la demande reste stable → pression haussière de long terme
        collection_inactive = not collection.get("active", True)
        signals["collection_inactive"] = collection_inactive
        if collection_inactive:
            score += 0.25

        # ── S2 : Tendance prix 7j/30j et 30j/90j ────────────────────────
        trend_7d_30d  = (avg_7d - avg_30d) / avg_30d  if avg_30d else 0
        trend_30d_90d = (avg_30d - avg_90d) / avg_90d if avg_90d else 0
        signals["trend_7d_30d"]  = round(trend_7d_30d,  3)
        signals["trend_30d_90d"] = round(trend_30d_90d, 3)

        if trend_7d_30d > 0.10:   score += 0.20   # +10% en 7j vs 30j
        elif trend_7d_30d > 0.05: score += 0.10   # +5% → signal modéré
        elif trend_7d_30d < -0.15: score -= 0.20  # en baisse forte → pénalité

        if trend_30d_90d > 0.10:  score += 0.10   # tendance de fond haussière

        # ── S3 : Accélération du volume (hype naissante) ─────────────────
        avg_vol_weekly = vol_30d / 4.3 if vol_30d else 0
        vol_accel      = (vol_7d / avg_vol_weekly - 1) if avg_vol_weekly > 0 else 0
        signals["volume_acceleration"] = round(vol_accel, 3)
        if vol_accel > 0.50:  score += 0.15   # volume 7j = 1.5× la moyenne → hype
        elif vol_accel > 0.25: score += 0.07

        # ── S4 : Pump score (supply faible + prix bas + collection inactive) ──
        # Formule communautaire : log(price) / log(supply_fn) > 17
        supply_fn = items.get("quantity_fn", supply)  # copies FN spécifiquement
        if supply_fn > 1 and price > 0:
            pump_score_val = log(price) / log(supply_fn)
            signals["pump_score"] = round(pump_score_val, 2)
            is_pump_candidate = (
                pump_score_val > 17
                and price < 150
                and collection_inactive
            )
            signals["pump_candidate"] = is_pump_candidate
            if is_pump_candidate:
                # Attention : double tranchant
                # Si le pump est déjà en cours → OUTPUT intéressant pour nos trade-ups
                # Si notre INPUT est pump-candidate → pénalité via detect_pump()
                score += 0.15
        else:
            signals["pump_score"]     = 0
            signals["pump_candidate"] = False

        # ── S5 : Saisonnalité calendaire ─────────────────────────────────
        month = date.today().month
        seasonal_label, seasonal_delta = self.SEASONAL_CALENDAR[month]
        signals["seasonal_phase"] = seasonal_label
        score += seasonal_delta

        # ── S6 : Corrélation inter-skins (propagation collection) ────────
        if peer_skins:
            peer_trends = []
            for peer in peer_skins:
                p_avg_7d  = peer.get("avg_7d",  0) or 0
                p_avg_30d = peer.get("avg_30d", 0) or 0
                if p_avg_30d:
                    peer_trends.append((p_avg_7d - p_avg_30d) / p_avg_30d)
            if peer_trends:
                avg_peer_trend = sum(peer_trends) / len(peer_trends)
                signals["peer_collection_trend"] = round(avg_peer_trend, 3)
                if avg_peer_trend > 0.08:
                    score += 0.08   # la collection entière est en hausse

        # ── S7 : Divergence cross-plateforme (V2 — BUFF163 requis) ───────
        buff_ratio = items.get("buff_skinport_ratio")   # prix_buff / prix_skinport
        if buff_ratio:
            signals["cross_platform_ratio"] = round(buff_ratio, 3)
            if buff_ratio < 0.70:
                # BUFF163 beaucoup moins cher que Skinport → sur-offre ou
                # arbitrageurs n'ont pas encore équilibré → signal baissier Skinport
                score -= 0.10
            elif buff_ratio > 0.90:
                # Prix proches → marché équilibré → signal stable
                pass

        # ── Score final et verdict ────────────────────────────────────────
        momentum_score = round(max(-0.5, min(1.0, score)), 3)

        if momentum_score > 0.55:   verdict = MomentumVerdict.STRONG_UP
        elif momentum_score > 0.30: verdict = MomentumVerdict.MODERATE_UP
        elif momentum_score > 0.10: verdict = MomentumVerdict.NEUTRAL
        else:                       verdict = MomentumVerdict.CAUTIOUS

        return {
            "momentum_score":    momentum_score,
            "verdict":           verdict,
            "signals":           signals,
            "display_label":     {
                MomentumVerdict.STRONG_UP:   "📈📈 fort signal haussier",
                MomentumVerdict.MODERATE_UP: "📈 signal haussier",
                MomentumVerdict.NEUTRAL:     "➡️  neutre",
                MomentumVerdict.CAUTIOUS:    "⚠️  conditions défavorables",
            }[verdict],
        }
```

---

#### Intégration dans le Kontract Score

Le momentum score de l'output est converti en **multiplicateur** appliqué après le calcul du score de base. Il amplifie les bonnes opportunités au bon moment et pénalise les situations défavorables.

```python
def momentum_to_multiplier(momentum_score: float) -> float:
    """
    Convertit le momentum score en multiplicateur pour le Kontract Score.
    Plage : 0.75 (très défavorable) → 1.30 (très favorable)

    Calibrage :
    - Neutre (0.0)  → 1.00 (aucun effet)
    - Fort (+0.55)  → 1.30 (+30% sur le score)
    - Défavorable (−0.30) → 0.80 (−20% sur le score)

    La transformation est linéaire par morceaux pour éviter des effets
    de seuil brusques.
    """
    if momentum_score >= 0:
        # Zone positive : +1% de score par point de momentum × 0.55
        return min(1.30, 1.0 + momentum_score * 0.545)
    else:
        # Zone négative : pénalité atténuée (asymétrie intentionnelle)
        return max(0.75, 1.0 + momentum_score * 0.500)

# Exemple :
# momentum_score = 0.55 → multiplier = 1.30 → Kontract Score × 1.30
# momentum_score = 0.00 → multiplier = 1.00 → Kontract Score inchangé
# momentum_score = -0.30 → multiplier = 0.85 → Kontract Score × 0.85
```

---

#### Calendrier saisonnier — données historiques

| Période | Signal | Impact moyen documenté | Durée |
|---------|--------|----------------------|-------|
| Steam Summer Sale (juin) | Hausse demande + cas openings | +15% sur skins populaires | 2–3 semaines |
| Steam Winter Sale (déc) | Idem | +10–20% | 2–3 semaines |
| Majors CS2 (mars, oct–nov) | Hausse stickers + skins teams | +20–30% sur skins liés | 1–2 semaines |
| Rentrée scolaire (sept) | Baisse activité joueurs | −5 à −10% | 3–4 semaines |
| Nouvelle case (variable) | Hausse supply → baisse inputs | −5 à −15% sur skins similaires | 1–2 semaines |
| Post-MAJ Valve (variable) | Choc volatilité | ±30% en 24h | Imprévisible |

> **Attention** : la saisonnalité représente un facteur d'amplification modéré (+/−15% max). Elle ne justifie pas à elle seule l'entrée ou la sortie d'une opportunité. Elle doit être combinée avec les autres signaux.

---

#### Modèle ML — V3 (XGBoost featurisé)

La recherche académique confirme que XGBoost avec features explicites surpasse les modèles LSTM sur ce marché. Features recommandées pour la V3 :

```python
FEATURES_XGBOOST_V3 = [
    # Prix relatifs (les plus prédictifs selon la thèse 2025)
    "price_vs_ma7",           # prix_actuel / MA7
    "price_vs_ma30",          # prix_actuel / MA30
    "price_vs_ma90",
    "price_deviation_3sigma", # (prix - MA30) / std30 — outlier score

    # Supply / structure (seconds en importance)
    "supply_total",           # quantité disponible toutes conditions
    "supply_fn_ratio",        # ratio FN / total
    "collection_active_bool",
    "case_age_days",          # ancienneté de la collection en jours

    # Volume
    "vol_accel_7d_30d",       # vol_7j / (vol_30j/4.3) - 1
    "vol_7d_30d_ratio",

    # Événements (one-hot encoding)
    "is_major_week",          # bool
    "is_steam_sale_period",   # bool
    "is_back_to_school",      # bool
    "days_since_last_update", # int

    # Corrélations marché
    "market_cap_7d_trend",    # tendance macro CSMarketCap
    "collection_avg_trend_7d",
    "cross_platform_ratio",   # ratio BUFF163 / Skinport (V3, BUFF requis)
]

TARGET = "price_change_7d_pct"   # régression : variation % à 7 jours
# Alternative classification : hausse > 5% dans les 7j (binaire)
```

> **Scope** : le modèle XGBoost est hors scope MVP et V1. Il nécessite un historique de prix d'au moins 6 mois (disponible via SteamAnalyst API ou accumulation interne) et BUFF163 pour le ratio cross-plateforme. Prévu en V3 quand la base de données interne est suffisamment riche.

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

#### Définition d'un slot

Un **slot** = un trade-up en cours d'acquisition. C'est simplement un panier d'inputs actif.

```
Slot 1 → Panier FAMAS REM → Fever Dream     (3/10 inputs achetés)
Slot 2 → Panier AK Redline → Asiimov        (7/10 inputs achetés)
Slot 3 → Panier USP Cortex → Black Tie      (10/10 → prêt à exécuter)
Slot 4 → vide
Slot 5 → vide
→ Slots occupés : 3 | Slots libres : 2
```

Quand un panier est exécuté dans CS2 et l'output reçu, le slot se **libère** immédiatement — disponible pour un nouveau trade-up.

**Il n'y a pas de limite technique** imposée par Valve ou Skinport. Le nombre de slots est un paramètre de configuration contraint par deux facteurs réels : le capital disponible et la capacité d'attention humaine.

---

#### Nombre de slots selon le capital — table de référence

| Capital total | Max engagé (30%) | Coût moyen inputs | Slots max capital | Slots recommandés |
|--------------|-----------------|------------------|------------------|------------------|
| 100€ | 30€ | 30€ | 1 | 1 |
| 200€ | 60€ | 40€ | 1 | 1 |
| 500€ | 150€ | 50€ | 3 | 2–3 |
| 500€ | 150€ | 80€ | 1 | 1–2 |
| 1 000€ | 300€ | 60€ | 5 | 3–5 |
| 2 000€ | 600€ | 80€ | 7 | 5 |
| 5 000€+ | 1 500€ | 100€ | 10+ | 5–7 |

> **Plafond humain** : au-delà de 5–7 slots simultanés, la gestion des alertes et des achats devient chronophage pour un trader individuel. Même avec un capital suffisant, la spec recommande de ne pas dépasser 5 slots en MVP.

---

#### Calcul automatique du nombre de slots optimal

```python
def compute_optimal_slots(
    bankroll:         float,
    avg_input_cost:   float,   # coût moyen d'un panier d'inputs (estimé sur les derniers trades)
    human_cap:        int = 5, # plafond humain — configurable
) -> dict:
    """
    Calcule le nombre de slots adapté au capital et au profil utilisateur.
    Retourne le nombre optimal ET la répartition du capital par slot.
    """
    capital_dispo  = bankroll * 0.30          # max 30% engagé
    max_par_slot   = bankroll * 0.20          # max 20% par trade-up
    per_slot       = min(avg_input_cost, max_par_slot)
    slots_capital  = int(capital_dispo / per_slot) if per_slot > 0 else 1
    slots_optimal  = min(slots_capital, human_cap)

    return {
        "slots_optimal":     max(1, slots_optimal),
        "capital_par_slot":  round(per_slot, 2),
        "capital_total_max": round(per_slot * slots_optimal, 2),
        "capital_reserve":   round(bankroll - per_slot * slots_optimal, 2),
        "ratio_engage":      round(per_slot * slots_optimal / bankroll, 2),
    }

# Exemples :
# compute_optimal_slots(200,  40) → slots=1, capital/slot=40€, réserve=160€
# compute_optimal_slots(500,  50) → slots=3, capital/slot=50€, réserve=350€
# compute_optimal_slots(500,  80) → slots=1, capital/slot=80€, réserve=420€
# compute_optimal_slots(1000, 60) → slots=5, capital/slot=60€, réserve=700€
# compute_optimal_slots(2000, 80) → slots=5, capital/slot=80€, réserve=1600€
```

---

#### Configuration portefeuille — une seule fois

```python
PORTFOLIO_CONFIG = {
    "bankroll":            500.0,   # budget total €
    "max_pct_bankroll":    0.30,    # jamais > 30% engagé simultanément
    "max_pct_per_tradeup": 0.20,    # max 20% du budget par trade-up
    "max_simultaneous":    5,       # plafond humain — indépendant du capital
    # max_simultaneous est le plafond absolu. Le nombre réel de slots actifs
    # est ensuite limité par le capital via compute_optimal_slots().
    "min_roi":             0.12,    # ROI minimum 12%
    "min_kontract_score":  8.0,     # seuil Kontract Score
    "float_crafting":      False,   # activé en V2
    "source_achat":        "skinport",
    "source_vente":        "skinport",
}

# Dérivés calculés automatiquement au démarrage
slots_config         = compute_optimal_slots(
                           PORTFOLIO_CONFIG["bankroll"],
                           avg_input_cost=60.0   # estimé ou saisi par l'utilisateur
                       )
max_capital_engaged  = slots_config["capital_total_max"]
max_per_tradeup      = PORTFOLIO_CONFIG["bankroll"] * PORTFOLIO_CONFIG["max_pct_per_tradeup"]
```

---

#### Signification de "slots libres" dans la décision hold/sell

```
Slots libres = max_simultaneous - len(active_baskets)

Slots libres = 0 → tous les paniers sont actifs
               → le capital restant NE PEUT PAS être réinvesti immédiatement
               → garder l'output en attente ne coûte rien en opportunité
               → seuil hold très bas → HOLD recommandé si momentum > 0.30

Slots libres ≥ 1 → au moins un slot disponible
               → du capital pourrait financer un nouveau panier
               → garder l'output bloque ce capital
               → seuil hold élevé → SELL recommandé sauf signal très fort
```

**Exemple avec 500€ / 3 slots calculés :**

```
Slot 1 → panier 50€ en cours
Slot 2 → panier 50€ en cours
Slot 3 → vide  ← 1 slot libre, ~50€ disponibles

Situation A : tu exécutes le slot 2 → slot 2 se libère → 2 slots libres
  → SELL NOW recommandé (coût opportunité sur 2 slots)

Situation B : tu exécutes le slot 2 pendant que le slot 1 vient d'ouvrir
  → même résultat : 2 slots libres → SELL NOW

Situation C : les 3 slots sont pleins ET tu exécutes pendant le hold
  → output reçu mais les 3 slots sont déjà ré-ouverts → SELL NOW

Situation D : 3 slots pleins, aucun nouveau trade-up dans le scanner > seuil
  → slots libres resteront libres → capital de toute façon inactif
  → HOLD recommandé si momentum > 0.30
```

---

---

#### PortfolioEngine — cycle principal

```python
class PortfolioEngine:
    """
    Moteur de portefeuille — tourne en continu.
    Cycle complet toutes les 5 minutes.
    WebSocket Skinport en temps réel pour les alertes d'achat, ActionRecommender 4.13 (plan d'actions Telegram avec items exacts + liens directs).
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
| Décision hold vs sell (OutputSellEngine) | ✓ recommandation | ✓ + stop-loss auto | ✓ + ML prédiction |

#### Schéma BDD — P&L enrichi

```sql
pnl_records :
    id               UUID PRIMARY KEY,
    basket_id        UUID REFERENCES trade_up_baskets(id),
    user_id          UUID,
    output_received  TEXT,
    output_float     DECIMAL(10,8),
    output_wear      TEXT,              -- FN / MW / FT / WW / BS
    sell_price       DECIMAL(10,2),     -- prix de vente réel final
    total_cost       DECIMAL(10,2),
    pnl_euros        DECIMAL(10,2),
    pnl_pct          DECIMAL(6,2),
    ev_calculated    DECIMAL(10,2),
    ev_accuracy      DECIMAL(6,3),     -- 1.0 = EV parfaitement réalisée
    float_predicted  DECIMAL(10,8),    -- float prédit par Kontract.gg
    float_delta      DECIMAL(10,8),    -- |float_réel - float_prédit|
    float_accurate   BOOLEAN,          -- delta <= 0.001
    detected_auto    BOOLEAN,          -- auto ou manuel
    executed_at      TIMESTAMP,
    -- Hold/Sell decision (OutputSellEngine)
    sell_decision         TEXT,        -- "sell_now" | "hold_N_days"
    sell_price_immediate  DECIMAL(10,2),-- prix au moment de la décision
    actual_sell_price     DECIMAL(10,2),-- prix réel (peut être différé si hold)
    actual_sell_date      TIMESTAMP,   -- date de vente réelle
    hold_days_target      INTEGER,     -- nb jours de hold visés
    hold_days_actual      INTEGER,     -- nb jours réellement attendus
    hold_gain_realized    DECIMAL(6,2),-- actual_sell vs sell_immediate (%)
    momentum_score_sell   DECIMAL(6,3),-- momentum au moment de la décision
    expected_gain_pct     DECIMAL(6,2),-- gain espéré lors de la décision
    hold_decision_quality TEXT         -- "correct"|"premature"|"too_long" (V2)
```


### 4.11 Module OutputSellEngine — décision hold vs vente immédiate

#### Problème : vélocité du capital vs gain marginal

Après l'exécution d'un trade-up, la question se pose : vendre immédiatement ou attendre si le prix de l'output semble devoir monter ? La réponse dépend d'un arbitrage mathématique précis entre le **gain d'attente espéré** et le **coût d'opportunité du capital immobilisé**.

**Formule fondamentale :**

```python
# Le gain d'attente est rentable seulement si :
# gain_espéré > roi_tradeup × (jours_attente / durée_cycle)

# Exemple : ROI 18%, cycle 5 jours, attente 3 jours, gain espéré +8%
# Seuil = 18% × (3/5) = 10.8%
# Gain espéré 8% < 10.8% → NE PAS ATTENDRE

# Contre-exemple avec slots pleins :
# Si le portefeuille est saturé (slots libres = 0), le capital ne peut pas
# être réinvesti de toute façon → seuil tombe à 0 → hold rationnel si
# momentum > 0.30
```

**Conclusion clé** : le hold conditionnel (uniquement quand les slots sont pleins ET le signal momentum est fort) est la stratégie optimale. Le hold systématique est toujours sous-optimal à cause de la perte de vélocité du capital.

> **Rappel** : un slot = un panier d'inputs actif. Le nombre de slots est calculé automatiquement selon le capital (`compute_optimal_slots()`). "Slots pleins" signifie que tous les paniers calculés sont actifs et que le capital disponible est déjà engagé — il n'y a rien à réinvestir immédiatement, donc garder l'output en attente est gratuit.

---

#### OutputSellEngine — implémentation

```python
class OutputSellEngine:
    """
    Décide quand vendre l'output d'un trade-up exécuté.
    Intègre le momentum (PriceSignalEngine), la vélocité du capital,
    et le risque Valve.
    Appelé automatiquement après chaque détection d'output (V1).
    """

    MAX_HOLD_DAYS       = 7      # jamais au-delà — prédictibilité < 50%
    MIN_MOMENTUM_HOLD   = 0.30   # seuil minimum pour envisager l'attente
    GAIN_CALIBRATION    = 0.18   # gain espéré par point momentum × nb_jours
    STOP_LOSS_PCT       = 0.05   # -5% → vente forcée pendant le hold

    def decide(
        self,
        output_skin:      dict,   # skin reçu (market_hash_name, vol_7d, etc.)
        execution_price:  float,  # prix de vente actuel sur Skinport
        roi_tradeup:      float,  # ROI du trade-up (ex: 0.18 pour +18%)
        cycle_days:       float,  # durée totale du cycle d'achat + exécution
        portfolio:        dict,   # état du portefeuille {active_baskets, max_slots}
        momentum:         dict,   # résultat PriceSignalEngine output
        market_context:   dict,   # {days_since_valve_update, ...}
    ) -> dict:

        free_slots        = portfolio["max_slots"] - len(portfolio["active_baskets"])
        mom_score         = momentum["momentum_score"]
        days_since_update = market_context.get("days_since_valve_update", 30)

        # ── Règles éliminatoires → vente immédiate ────────────────────────
        if mom_score < self.MIN_MOMENTUM_HOLD:
            return self._sell(execution_price, "momentum_trop_faible")

        if days_since_update < 7:
            return self._sell(execution_price, "risque_valve_eleve_post_update")

        if output_skin.get("vol_7d", 0) < 10:
            return self._sell(execution_price, "output_peu_liquide")

        # ── Trouver l'horizon de hold optimal ─────────────────────────────
        for hold_days in [1, 2, 3, 5, 7]:
            expected_gain  = mom_score * self.GAIN_CALIBRATION * hold_days

            # Seuil de base : gain minimum pour justifier l'attente
            breakeven = roi_tradeup * (hold_days / max(cycle_days, 1))

            # Coût d'opportunité si des slots sont libres
            # (capital qui pourrait financer un nouveau trade-up)
            if free_slots > 0:
                # On estime à 50% la probabilité de trouver une opportunité
                opp_cost = (roi_tradeup / cycle_days) * hold_days * free_slots * 0.5
            else:
                # Slots pleins → capital de toute façon immobilisé
                opp_cost = 0

            total_threshold = breakeven + opp_cost

            if expected_gain > total_threshold:
                stop_loss_price = execution_price * (1 - self.STOP_LOSS_PCT)
                return {
                    "decision":        "hold",
                    "hold_days":       hold_days,
                    "expected_gain":   round(expected_gain * 100, 1),
                    "threshold":       round(total_threshold * 100, 1),
                    "reason":          (
                        f"gain_{expected_gain*100:.1f}% > "
                        f"seuil_{total_threshold*100:.1f}% "
                        f"(slots_libres={free_slots})"
                    ),
                    "stop_loss":       round(stop_loss_price, 2),
                    "review_at_days":  hold_days,
                }

        return self._sell(execution_price, "aucun_horizon_rentable")

    def _sell(self, price: float, reason: str) -> dict:
        return {
            "decision":   "sell_now",
            "sell_price": price,
            "reason":     reason,
        }

    def check_stop_loss(
        self,
        current_price: float,
        entry_price:   float,  # prix au moment de la décision de hold
        hold_days:     int,
        days_elapsed:  int,
        momentum:      dict,
    ) -> tuple[bool, str]:
        """
        Réévaluation périodique pendant le hold.
        Retourne (True, raison) si vente forcée recommandée.
        Appelé toutes les 5 min via APScheduler pendant la période de hold.
        """
        if current_price < entry_price * (1 - self.STOP_LOSS_PCT):
            return True, f"stop_loss_-{self.STOP_LOSS_PCT*100:.0f}%"

        if momentum["momentum_score"] < 0.15:
            return True, "momentum_disparu"

        if days_elapsed >= hold_days:
            return True, "duree_max_atteinte"

        if momentum.get("signals", {}).get("velocity_alert"):
            # Les inputs du trade-up suivant montent → réinvestir maintenant
            return True, "recipe_velocity_detectee"

        return False, "hold_continue"
```

---

#### Pipeline complet post-exécution

```python
async def handle_output_received(
    basket:         dict,
    output_item:    dict,
    float_val:      float,
    portfolio:      dict,
    prices:         dict,
    history:        dict,
    collections_db: dict,
):
    """
    Pipeline déclenché automatiquement après détection de l'output.
    Enchaîne : P&L immédiat → momentum → décision hold/sell → notification.
    """
    # 1. Calculer le P&L immédiat
    sell_price  = prices[output_item["market_hash_name"]]["min_price"]
    total_cost  = basket.state.total_spent
    pnl_imm     = sell_price * (1 - FEES["skinport"]["seller"]) - total_cost
    roi_imm     = pnl_imm / total_cost

    # 2. Calcul du momentum output
    collection  = collections_db[output_item["collection_id"]]
    output_hist = history.get(output_item["market_hash_name"], {})
    output_items = prices.get(output_item["market_hash_name"], {})

    momentum = PriceSignalEngine().compute_output_momentum(
        output_skin  = output_item,
        collection   = collection,
        history      = output_hist,
        items        = output_items,
        peer_skins   = get_peer_skins(collection, output_item),
    )

    # 3. Décision hold vs vente
    engine   = OutputSellEngine()
    decision = engine.decide(
        output_skin     = output_item,
        execution_price = sell_price,
        roi_tradeup     = roi_imm,
        cycle_days      = basket.cycle_days,
        portfolio       = portfolio,
        momentum        = momentum,
        market_context  = {"days_since_valve_update": get_days_since_update()},
    )

    # 4. Enregistrer la décision en BDD
    await db.update_pnl_record(basket["id"], {
        "sell_decision":    decision["decision"],
        "sell_price_imm":   sell_price,
        "hold_days_target": decision.get("hold_days", 0),
        "momentum_score":   momentum["momentum_score"],
        "expected_gain":    decision.get("expected_gain", 0),
    })

    # 5. Si hold → programmer la réévaluation périodique
    if decision["decision"] == "hold":
        await schedule_hold_monitoring(basket["id"], decision["hold_days"], engine)

    # 6. Notification Telegram
    await notify_sell_decision(basket, output_item, float_val,
                                pnl_imm, roi_imm, momentum, decision)
```

---

#### Notification Telegram — décision hold/sell

```
✅ Output détecté — AWP Fever Dream FT (float 0.247)

Coût inputs   : 19.00€
Valeur actuel : 22.40€
P&L immédiat  : +3.40€ (+17.9%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANALYSE HOLD vs VENTE

Momentum output : 📈 +0.52
  → Collection inactive depuis 18 mois
  → Tendance prix +8% (7j/30j)
  → Steam Summer Sale actif (+15% saisonnier)

Slots disponibles : 1/5 libres (coût opportunité actif)
Gain espéré hold 3j : +7.5%
Seuil rentabilité  : +10.8%  ← gain < seuil

💡 RECOMMANDATION : VENDRE MAINTENANT
   (Si tous les slots étaient pleins → HOLD 3j recommandé)

[✅ VENDRE] → https://skinport.com/item/...
[⏳ HOLD 3j] → stop-loss à 21.28€ (-5%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Si l'utilisateur choisit HOLD et que le stop-loss se déclenche :

```
⛔ Stop-loss déclenché — AWP Fever Dream FT
Prix actuel : 21.20€ (−5.4% vs entrée 22.40€)
→ Vente recommandée immédiatement pour limiter la perte
→ P&L final estimé : +2.00€ (+10.5%)

[VENDRE MAINTENANT]
```

---

#### Commandes Telegram

```
/sell <basket_id>              → vente immédiate au prix actuel
/hold <basket_id> <nb_jours>   → activer hold manuel avec stop-loss auto
/hold_status                   → voir tous les outputs en attente
```

---

#### Schéma BDD — colonnes additionnelles pnl_records

```sql
-- Colonnes supplémentaires ajoutées à pnl_records pour le tracking hold/sell
sell_decision         TEXT,         -- "sell_now" | "hold_N_days"
sell_price_immediate  DECIMAL(10,2),-- prix au moment de la décision
actual_sell_price     DECIMAL(10,2),-- prix de vente réel (peut être différé)
actual_sell_date      TIMESTAMP,    -- date de vente réelle
hold_days_target      INTEGER,      -- nb jours de hold visés (si hold)
hold_days_actual      INTEGER,      -- nb jours réellement attendus
hold_gain_realized    DECIMAL(6,2), -- actual_sell - sell_immediate (en %)
momentum_score_sell   DECIMAL(6,3), -- momentum au moment de la décision
expected_gain_pct     DECIMAL(6,2), -- gain espéré au moment de la décision
hold_decision_quality TEXT          -- "correct" | "premature" | "too_long"
                                    -- calculé rétrospectivement (V2)
```

---

#### Tableau automatisation par phase — hold/sell

| Étape | MVP | V1 | V2 |
|-------|-----|----|----|
| Calcul P&L immédiat | ✓ | ✓ | ✓ |
| Momentum output (PriceSignalEngine) | ✓ | ✓ | ✓ |
| Décision hold/sell automatique | ✓ | ✓ | ✓ |
| Notification Telegram avec recommandation | ✓ | ✓ | ✓ |
| Monitoring stop-loss pendant hold | ✗ | ✓ polling 5min | ✓ |
| Réévaluation momentum pendant hold | ✗ | ✓ | ✓ |
| Qualité décision rétroactive | ✗ | ✗ | ✓ auto |
| Modèle ML prédiction gain hold | ✗ | ✗ | ✓ XGBoost V3 |

### 4.14 Interface utilisateur — architecture des pages

L'interface MVP (Streamlit) est organisée en **4 pages** accessibles via une sidebar. Chaque page correspond à une phase du workflow utilisateur.

---

#### Page 0 — Plan d'action (page d'accueil)

C'est le **cockpit principal** de Kontract.gg. Elle agrège toutes les actions concrètes du moment, triées par urgence. L'utilisateur n'a aucune décision à prendre — juste cliquer sur les liens.

Navigation mise à jour :
```
Sidebar : 📋 Plan  |  🔍 Scanner  |  📦 Portefeuille  |  🔢 Calculateur  |  📊 P&L
```

```
┌─────────────────────────────────────────────────────────────────────┐
│ 🎯 KONTRACT.GG   Plan  Scanner  Portefeuille  Calculateur  P&L      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  📋 PLAN D'ACTION — Vendredi 20 mars · 14h32                        │
│  Mis à jour il y a 2min | 3 slots actifs / 3 | Capital 423/500€     │
│  ⚠️  Risque Valve permanent — toute MAJ peut invalider les actions   │
│                                                                      │
│  ┌── 🔴 URGENT (2) ───────────────────────────────────────────┐     │
│  │                                                             │     │
│  │ [1] 🛒 ACHETER MAINTENANT                                   │     │
│  │     FAMAS | Rapid Eye Movement (Minimal Wear)               │     │
│  │     Float 0.1430 · Score listing 84/100                     │     │
│  │     Prix 7.93€  (−17% vs médiane)  ·  Skinport              │     │
│  │     Panier : FAMAS REM→Fever Dream FN  ·  Input 3/10        │     │
│  │     ⏱ Expire ~2h (vol 8 ventes/j)                          │     │
│  │     [🛒 ACHETER] → skinport.com/item/.../6934215            │     │
│  │                                                             │     │
│  │ [2] 🛒 ACHETER MAINTENANT                                   │     │
│  │     FAMAS | Rapid Eye Movement (Minimal Wear)               │     │
│  │     Float 0.1460 · Score 79/100 · 7.95€ (−17%)             │     │
│  │     Panier : idem  ·  Input 4/10 après cet achat            │     │
│  │     [🛒 ACHETER] → skinport.com/item/.../6934221            │     │
│  │                                                             │     │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌── 🟡 CE SOIR (3) ──────────────────────────────────────────┐     │
│  │                                                             │     │
│  │ [3] 👁 SURVEILLER — acheter si prix ≤ 8.10€                │     │
│  │     FAMAS | Rapid Eye Movement (Minimal Wear)               │     │
│  │     Prix actuel 8.39€  ·  Cible : < 8.10€                  │     │
│  │     Panier : FAMAS REM→Fever Dream FN  ·  Input 5/10        │     │
│  │     [👁 SURVEILLER] → skinport.com/market/...               │     │
│  │                                                             │     │
│  │ [4] 💰 VENDRE MAINTENANT                                    │     │
│  │     AWP | Fever Dream (Field-Tested)  ·  float 0.247        │     │
│  │     Prix actuel 22.40€ · Momentum 📈 mais slot libre        │     │
│  │     Raison : gain espéré +7.5% < seuil +10.8%              │     │
│  │     [💰 VENDRE] → skinport.com/sell  [⏳ HOLD 3j]          │     │
│  │                                                             │     │
│  │ [5] ✅ EXÉCUTER LE TRADE-UP DANS CS2                        │     │
│  │     M4A4 Howl input → AWP Dragon Lore BS  ·  10/10 ✓        │     │
│  │     Float prédit 0.521 → Battle-Scarred                     │     │
│  │     [📋 VOIR INSTRUCTIONS CS2]                              │     │
│  │                                                             │     │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌── 🟠 ATTENTION (1) ────────────────────────────────────────┐     │
│  │                                                             │     │
│  │ [6] ⚠️  ABANDON RECOMMANDÉ                                  │     │
│  │     Glock | Bullet Rain → Dragon King                       │     │
│  │     Score 8.3 (était 14.2)  ·  4/10 inputs achetés         │     │
│  │     Perte abandon −4.20€  ·  EV restante +2.80€            │     │
│  │     [❌ ABANDONNER et revendre] [↩️ Ignorer]               │     │
│  │                                                             │     │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌── 🟢 CETTE SEMAINE (1) ────────────────────────────────────┐     │
│  │                                                             │     │
│  │ [7] 🆕 NOUVELLE OPPORTUNITÉ — 1 slot se libère bientôt     │     │
│  │     USP Cortex → Black Tie  ·  Score 14.1  ·  ROI +24%     │     │
│  │     Momentum ⚠️ −8% (rentrée scolaire)                     │     │
│  │     Premier input à acheter :                               │     │
│  │     USP-S | Cortex (FT) float=0.201 · 8.20€ · score 73     │     │
│  │     [🛒 OUVRIR CE PANIER] → skinport.com/item/.../7890123   │     │
│  │                                                             │     │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  [🔄 Rafraîchir]  [⚙️ Préférences]  Actions expirées auj. : 3       │
└─────────────────────────────────────────────────────────────────────┘
```

**Comportements dynamiques :**
- Rafraîchissement automatique toutes les 5 min (APScheduler)
- Alerte WebSocket instantanée pour les actions urgentes (score ≥ 80) — badge rouge sur l'onglet "Plan"
- Les actions expirées (listing vendu, hold terminé) disparaissent automatiquement
- La priorité URGENT n'apparaît que si des actions sont disponibles maintenant

**Vue détail — Exécution CS2 (clic sur [📋 VOIR INSTRUCTIONS CS2]) :**

```
┌─────────────────────────────────────────────────────────────────────┐
│  ✅ PANIER PRÊT — M4A4 Howl in → AWP Dragon Lore BS                 │
├─────────────────────────────────────────────────────────────────────┤
│  10/10 inputs dans l'inventaire ✓                                   │
│  Float output prédit : 0.521 → Battle-Scarred                       │
│  EV nette estimée    : +14.20€  (+18% ROI)                          │
│                                                                      │
│  INSTRUCTIONS CS2 :                                                  │
│  1. Ouvrir CS2 → Inventaire → onglet "Contrats"                     │
│  2. Glisser ces 10 items dans les emplacements :                     │
│     ✓ M4A4|Howl FT float=0.289  assetid:24958657824                 │
│     ✓ M4A4|Howl FT float=0.301  assetid:24958657901                 │
│     ... (10 lignes)                                                  │
│  3. Vérifier float CS2 ≈ 0.521                                      │
│  4. Cliquer "Envoyer le contrat"                                     │
│                                                                      │
│  [✅ J'AI EXÉCUTÉ → confirmer /executed auto]                       │
└─────────────────────────────────────────────────────────────────────┘
```

**Vue détail — Abandon (clic sur [❌ ABANDONNER]) :**

```
┌─────────────────────────────────────────────────────────────────────┐
│  ⚠️  ABANDON — Glock | Bullet Rain → Dragon King                    │
├─────────────────────────────────────────────────────────────────────┤
│  4/10 inputs achetés  ·  38€ investis                               │
│  Perte si abandon : −4.20€  |  EV si continue : +2.80€             │
│  → Abandonner économise 1.40€ vs continuer                          │
│                                                                      │
│  REVENDRE CES 4 ITEMS :                                              │
│  [1] Glock|Bullet Rain MW float=0.124  9.20€  → skinport.com/...    │
│  [2] Glock|Bullet Rain MW float=0.139  9.15€  → skinport.com/...    │
│  [3] Glock|Bullet Rain MW float=0.131  9.20€  → skinport.com/...    │
│  [4] Glock|Bullet Rain MW float=0.147  9.10€  → skinport.com/...    │
│  Total estimé revente : 33.80€  (perte nette : −4.20€)             │
│                                                                      │
│  [❌ CONFIRMER ABANDON]   [↩️ IGNORER et continuer]                 │
└─────────────────────────────────────────────────────────────────────┘
```

**Vue détail — Stratégie fillers (clic sur [🛒 OUVRIR CE PANIER]) :**

```
┌─────────────────────────────────────────────────────────────────────┐
│  🆕 OUVRIR — FAMAS REM → AWP Fever Dream FN  (stratégie fillers 7+3)│
├─────────────────────────────────────────────────────────────────────┤
│  Kontract Score 36.4  ·  ROI +18%  ·  Budget estimé 63.51€         │
│  Momentum 📈📈 +57% (collection inactive + Steam Summer Sale)       │
│  Float output prédit : Battle-Scarred (avg_norm ≈ 0.87)             │
│                                                                      │
│  INPUTS COLLECTION CIBLE (7×)                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ # │ Item                        │Float │Score│ Prix  │ Lien│     │
│  │ 1 │ FAMAS|REM (MW)              │0.143 │ 84  │ 7.93€ │ [🛒]│     │
│  │ 2 │ FAMAS|REM (MW)              │0.146 │ 79  │ 7.95€ │ [🛒]│     │
│  │ 3 │ FAMAS|REM (MW)              │0.137 │ 71  │ 8.00€ │ [🛒]│     │
│  │ 4 │ FAMAS|REM (MW)              │0.144 │ 69  │ 8.00€ │ [🛒]│     │
│  │ 5 │ FAMAS|REM (MW)              │0.139 │ 65  │ 8.32€ │ [🛒]│     │
│  │ 6 │ FAMAS|REM (MW)              │0.125 │ 63  │ 8.41€ │ [🛒]│     │
│  │ 7 │ FAMAS|REM (MW)              │0.132 │ 61  │ 8.39€ │ [🛒]│     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                      │
│  FILLERS (3×) — collection Genesis, float range max 0.00–1.00       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ # │ Item                        │Float │Score│ Prix  │ Lien│     │
│  │ 8 │ MP5-SD|Focus (MW)           │0.112 │ 72  │ 0.84€ │ [🛒]│     │
│  │ 9 │ MP5-SD|Focus (MW)           │0.098 │ 70  │ 0.86€ │ [🛒]│     │
│  │10 │ MP5-SD|Focus (MW)           │0.124 │ 68  │ 0.89€ │ [🛒]│     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                      │
│  Coût total estimé : 63.51€  ·  EV nette : +11.43€  ·  ROI : +18%  │
│  [🛒 TOUT ACHETER EN ORDRE] (liens s'ouvrent séquentiellement)       │
└─────────────────────────────────────────────────────────────────────┘
```

---

#### Page 1 — Scanner (opportunités)

Vue de toutes les opportunités qualifiées, triées par Kontract Score décroissant. Disponible pour les utilisateurs qui veulent explorer au-delà du plan d'action suggéré.

```
┌─────────────────────────────────────────────────────────────────────┐
│  🔍 SCANNER   Plan  Scanner  Portefeuille  Calculateur  P&L          │
├─────────────────────────────────────────────────────────────────────┤
│  FILTRES                                                              │
│  ROI min [10%▼]  Budget [100€▼]  Pool max [5▼]  Score min [5▼]      │
│  [✓] Exclure trending_down  [ ] Exclure haute volatilité             │
│  Stratégie : [Toutes ▼]  Source achat : [Skinport ▼]                 │
│                                                                       │
│  42 opportunités  ·  Mis à jour il y a 2min                          │
│  ⚠️  Risque Valve permanent                                           │
│                                                                       │
│  Score │ Trade-up                   │ROI  │Pool│Vol/j│Inputs│Moment.│
│  ──────┼────────────────────────────┼─────┼────┼─────┼──────┼─────  │
│  36.4  │ FAMAS REM → Fever Dream FN │+18% │ 2  │ 38  │🟢 x40│📈📈+57%│
│  28.1  │ AK Redline → Asiimov FT    │+22% │ 3  │ 95  │🟢 x80│📈 +30%│
│  18.9  │ M4A4 Howl → Dragon         │+15% │ 2  │ 12  │🟡 x8 │➡️  +0%│
│  ⚡14.1 │ USP Cortex → Black Tie     │+24% │ 4  │ 44  │🟢 x55│⚠️  -8%│
│  ...                                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

**⚡ = recipe velocity alert** (inputs en hausse rapide)

Clic sur une ligne → **panneau de détail latéral** :

```
┌── DÉTAIL OPPORTUNITÉ — FAMAS REM → AWP Fever Dream FN ──────────────┐
│  Kontract Score : 36.4  ·  ROI : +18%  ·  Momentum : 📈📈 +57%      │
│  EV nette : +9.20€  ·  Win prob : 85%  ·  Floor ratio : 42%         │
│  Pool : 2 outcomes  ·  Cycle estimé : 5 jours                        │
│                                                                       │
│  OUTCOMES                                                             │
│  AWP Fever Dream FN   12%  ·  42.00€  ·  vol 7j:15  ·  ✓ win        │
│  AWP Fever Dream MW   88%  ·  18.00€  ·  vol 7j:38  ·  ✓ win        │
│                                                                       │
│  SIGNAUX MARCHÉ                                                       │
│  Collection inactive ✓  ·  Trend +8%  ·  Steam Summer Sale actif     │
│  Pump score : 14.2 (normal)  ·  Recipe velocity : stable ✓           │
│                                                                       │
│  TOP 3 LISTINGS INPUT — FAMAS | REM (Minimal Wear)                   │
│  # │Score│ Float  │  Prix  │Saving│ Action                           │
│  1 │ 84  │ 0.1430 │ 7.93€  │ −17% │ [🛒 Acheter]                    │
│  2 │ 79  │ 0.1460 │ 7.95€  │ −17% │ [🛒 Acheter]                    │
│  3 │ 71  │ 0.1370 │ 8.00€  │ −17% │ [🛒 Acheter]                    │
│                                                                       │
│  Kelly recommandé : 2.3% du bankroll  ·  Répétable : 8×              │
│                                                                       │
│  [➕ Ajouter au portefeuille]  [🔢 Ouvrir dans le calculateur]       │
└─────────────────────────────────────────────────────────────────────┘
```


#### Page 2 — Portefeuille (gestion des paniers actifs)

Vue en temps réel de tous les paniers en cours pour l'utilisateur.

```
┌─────────────────────────────────────────────────────────────────────┐
│  📦 PORTEFEUILLE  Plan  Scanner  Portefeuille  Calculateur  P&L      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Capital : 423€ engagé / 500€ max (3 slots) ████████░░░░░░░░░░░░░    │
│  Slots  : 3 / 3 actifs  ← tous pleins  |  0 slot libre               │
│  (Chaque slot ≈ 80€ d'inputs | Capital réserve : 77€)                │
│                                                                       │
│  Score  │ Trade-up              │Panier │Budget│Statut   │Action     │
│  ───────┼───────────────────────┼───────┼──────┼─────────┼─────────  │
│  24.7   │ FAMAS → Fever Dream   │ 3/10  │ 24€  │🔄 achat │[Détail]  │
│  21.3   │ AK → Asiimov FT       │ 7/10  │ 62€  │🔄 achat │[Détail]  │
│  18.9   │ M4A4 → Dragon         │10/10  │ 98€  │✅ PRÊT  │[Exécuter]│
│  15.2   │ FAMAS → Fever Dream   │Vendu  │  -   │⏳ HOLD 2j│ 22.40€  │[Vendre]  │
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
│  🔢 CALCULATEUR   Plan  Scanner  Portefeuille  Calculateur  P&L      │
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
│  📊 P&L & STATS   Plan  Scanner  Portefeuille  Calculateur  P&L      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  RÉSUMÉ                        30 derniers jours                     │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐            │
│  │ +142.30€ │  78%     │ +16.2%   │  94%     │  4.2j    │            │
│  │ P&L net  │ Win rate │ ROI moy  │ Préc. EV │ Cycle moy│            │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘            │
│  Slots actifs : 3/3 | Vélocité capital : 87% (taux d'occupation)    │
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
| **Plan d'action** | ✓ Page d'accueil + Telegram | ✓ + vues détail abandon/exécution | ✓ Push temps réel + badges |
| Scanner | ✓ Complet | ✓ + filtres perso | ✓ UX améliorée |
| Portefeuille | ✓ Basique (sync manuel) | ✓ + sync Steam auto | ✓ WebSocket temps réel |
| Calculateur | ✓ Complet | ✓ + float crafting | ✓ |
| P&L & Stats | ✗ (phase V1) | ✓ Table simple | ✓ Graphiques interactifs |

---

### 4.13 Module ActionRecommender — Quoi acheter/vendre, quand, où

#### Architecture du module en détail

Le module ActionRecommender est la **couche de sortie finale** de Kontract.gg. Il agrège tous les signaux calculés en amont (Kontract Score, PriceSignalEngine, score hybride listings, OutputSellEngine, slots disponibles) pour produire une liste d'actions concrètes et priorisées.

Chaque action est un **item exact** avec un lien direct, un prix cible, un timing, et une plateforme. L'utilisateur n'a aucune décision à prendre — juste à exécuter.

```
INPUT  → Tous les modules amont (scanner, portefeuille, momentum, sell engine)
OUTPUT → Liste d'actions triées par priorité :
         [ACHETER maintenant] FAMAS REM MW float=0.143 — 7.93€ → lien Skinport
         [ACHETER ce soir]    FAMAS REM MW float=0.146 — si prix < 8.10€
         [VENDRE maintenant]  AWP Fever Dream FT → 22.40€ sur Skinport
         [ATTENDRE]           AK Redline FT — inputs en hausse, patienter 48h
```

---

#### Architecture du module

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime, timedelta

class ActionType(str, Enum):
    BUY_NOW      = "buy_now"       # achat immédiat recommandé
    BUY_WATCH    = "buy_watch"     # surveiller — acheter si prix descend
    BUY_WAIT     = "buy_wait"      # attendre avant d'acheter (signal défavorable)
    SELL_NOW     = "sell_now"      # vendre immédiatement
    SELL_HOLD    = "sell_hold"     # garder encore N jours
    SELL_WATCH   = "sell_watch"    # surveiller le prix avant de vendre
    EXECUTE      = "execute"       # panier complet → exécuter le trade-up dans CS2
    ABANDON      = "abandon"       # abandonner le panier, revendre les inputs

class ActionPriority(str, Enum):
    URGENT   = "urgent"    # fenêtre de quelques minutes (listing rare, prix optimal)
    HIGH     = "high"      # agir dans les prochaines heures
    NORMAL   = "normal"    # agir dans la journée
    LOW      = "low"       # agir cette semaine

@dataclass
class Action:
    """Représente une action concrète à exécuter."""
    type:          ActionType
    priority:      ActionPriority

    # Identification de l'item EXACT
    market_hash_name: str          # ex: "FAMAS | Rapid Eye Movement (Minimal Wear)"
    sale_id:          Optional[str] # ID unique du listing Skinport (si BUY_NOW)
    assetid:          Optional[str] # assetid Steam (si item déjà en inventaire)

    # Prix et plateforme
    platform:         str           # "skinport" | "steam" | "buff163"
    price:            float          # prix exact du listing
    price_target:     Optional[float] # seuil d'achat pour BUY_WATCH
    url:              str            # lien direct vers le listing ou la page vente

    # Contexte et justification
    basket_id:        Optional[str]  # panier associé (si achat input)
    opportunity_name: str            # ex: "FAMAS REM → AWP Fever Dream FN"
    reason:           str            # justification en clair
    score:            float          # score de priorité 0–100

    # Float (si pertinent)
    float_val:        Optional[float]
    float_norm:       Optional[float]

    # Timing
    expires_at:       Optional[datetime]  # après cette date, l'action est caduque
    valid_until_price: Optional[float]    # valide tant que le prix reste en dessous

    # Metadata
    created_at:       datetime
    listing_score:    Optional[float]  # score hybride du listing (buy actions)
```

---

#### ActionRecommender — générateur d'actions

```python
class ActionRecommender:
    """
    Agrège tous les signaux pour produire la liste d'actions prioritaires.
    Exécuté à chaque cycle de 5 min (APScheduler) + en temps réel (WebSocket).
    """

    def generate_action_plan(
        self,
        portfolio:      dict,
        opportunities:  list,
        prices:         dict,
        history:        dict,
        collections_db: dict,
        user_config:    dict,
    ) -> list[Action]:
        """
        Point d'entrée principal. Retourne la liste complète des actions
        triées par score décroissant (plus urgent en premier).
        """
        actions = []

        # 1. Actions d'achat pour les paniers actifs
        for basket in portfolio["active_baskets"]:
            actions += self._buy_actions(basket, prices, history)

        # 2. Actions de vente pour les outputs en attente
        for output in portfolio["pending_outputs"]:
            actions += self._sell_actions(output, prices, history,
                                           collections_db, portfolio)

        # 3. Actions d'exécution (paniers complets)
        for basket in portfolio["active_baskets"]:
            if basket.state.is_complete:
                actions.append(self._execute_action(basket))

        # 4. Actions d'abandon (paniers dont le score a trop chuté)
        for basket in portfolio["active_baskets"]:
            should_quit, reason = should_abandon_basket(
                basket.state,
                basket.opportunity,
                user_config["min_kontract_score"],
                prices,
            )
            if should_quit:
                actions += self._abandon_actions(basket, prices, reason)

        # 5. Nouvelles opportunités à ouvrir si slots disponibles
        free_slots = portfolio["slots_optimal"] - len(portfolio["active_baskets"])
        if free_slots > 0:
            actions += self._new_opportunity_actions(
                opportunities, portfolio, free_slots, prices, history, collections_db
            )

        # Trier par score décroissant
        return sorted(actions, key=lambda a: -a.score)


    # ──────────────────────────────────────────────────────────────────────
    # ACTIONS D'ACHAT — inputs pour les paniers actifs
    # ──────────────────────────────────────────────────────────────────────

    def _buy_actions(
        self,
        basket: dict,
        prices: dict,
        history: dict,
    ) -> list[Action]:
        """
        Pour chaque input manquant dans le panier, trouve le meilleur
        listing disponible et génère une action d'achat concrète.
        """
        actions = []
        target   = basket.opportunity
        state    = basket.state
        n_needed = state.n_remaining

        for skin_needed in target["inputs_required"]:
            if state._skin_already_bought(skin_needed["market_hash_name"]):
                continue

            # Récupérer les listings disponibles (via WebSocket cache)
            listings = self._get_cached_listings(skin_needed["market_hash_name"])
            if not listings:
                continue

            # Appliquer hard filters + score hybride
            ranked = rank_input_listings(
                raw_listings = listings,
                target       = {
                    **skin_needed,
                    "median_price":    prices[skin_needed["id"]]["median_price"],
                    "max_input_price": target["max_input_price"],
                    "stattrak":        target["stattrak"],
                    "float_crafting":  target.get("float_crafting", False),
                    "norm_min":        target.get("norm_min", 0),
                    "norm_max":        target.get("norm_max", 1),
                    "norm_center":     target.get("norm_center", 0.5),
                },
                panier_state = {
                    "n_bought":      state.n_bought,
                    "floats_bought": state.floats_bought,
                    "avg_price":     state.avg_price_bought,
                },
                top_n = 3,
            )

            for rank, listing in enumerate(ranked["top_listings"]):
                if listing["score"] < 60:
                    break  # en-dessous du seuil — ne pas recommander

                # Construire l'URL directe vers le listing
                url = f"https://skinport.com/item/{listing['url']}/{listing['sale_id']}"

                # Urgence basée sur le score et la liquidité
                priority = (
                    ActionPriority.URGENT if listing["score"] >= 80 and rank == 0
                    else ActionPriority.HIGH if listing["score"] >= 70
                    else ActionPriority.NORMAL
                )

                # L'action expire quand le listing sera probablement vendu
                # Sur un skin avec vol_24h=8, un listing dure ~1–3h en moyenne
                vol_24h  = history.get(skin_needed["market_hash_name"],
                                       {}).get("last_24_hours", {}).get("volume", 1)
                ttl_hours = max(0.5, 24 / max(vol_24h, 1))
                expires   = datetime.utcnow() + timedelta(hours=ttl_hours)

                actions.append(Action(
                    type             = ActionType.BUY_NOW,
                    priority         = priority,
                    market_hash_name = listing["market_hash_name"],
                    sale_id          = listing["sale_id"],
                    assetid          = None,
                    platform         = "skinport",
                    price            = listing["price"],
                    price_target     = None,
                    url              = url,
                    basket_id        = basket["id"],
                    opportunity_name = target["name"],
                    reason           = (
                        f"Input {state.n_bought+1}/{state.n_required} "
                        f"— score listing {listing['score']}/100 "
                        f"({listing['price_saving_pct']:+.1f}% vs médiane)"
                    ),
                    score          = listing["score"],
                    float_val      = listing.get("float_val"),
                    float_norm     = listing.get("float_norm"),
                    expires_at     = expires,
                    valid_until_price = listing["price"] * 1.03,  # valide si prix < +3%
                    created_at     = datetime.utcnow(),
                    listing_score  = listing["score"],
                ))

        return actions


    # ──────────────────────────────────────────────────────────────────────
    # ACTIONS DE VENTE — outputs reçus
    # ──────────────────────────────────────────────────────────────────────

    def _sell_actions(
        self,
        output:         dict,
        prices:         dict,
        history:        dict,
        collections_db: dict,
        portfolio:      dict,
    ) -> list[Action]:
        """
        Pour chaque output en attente, décide de la stratégie optimale
        de vente et génère l'action concrète.
        """
        skin_name    = output["market_hash_name"]
        current_price = prices.get(skin_name, {}).get("min_price", 0)
        if not current_price:
            return []

        # Calculer le momentum output
        coll_id    = output.get("collection_id")
        collection = collections_db.get(coll_id, {})
        hist_out   = history.get(skin_name, {})
        momentum   = PriceSignalEngine().compute_output_momentum(
            output_skin  = output,
            collection   = collection,
            history      = hist_out,
            items        = prices.get(skin_name, {}),
            peer_skins   = [],
        )

        # Décision hold vs sell
        engine   = OutputSellEngine()
        decision = engine.decide(
            output_skin      = output,
            execution_price  = current_price,
            roi_tradeup      = output.get("roi_tradeup", 0.18),
            cycle_days       = output.get("cycle_days", 5),
            portfolio        = portfolio,
            momentum         = momentum,
            market_context   = {"days_since_valve_update": get_days_since_update()},
        )

        if decision["decision"] == "sell_now":
            # Choisir la meilleure plateforme de vente
            sell_platform, sell_url = self._best_sell_platform(skin_name, current_price)

            return [Action(
                type             = ActionType.SELL_NOW,
                priority         = ActionPriority.HIGH,
                market_hash_name = skin_name,
                sale_id          = None,
                assetid          = output.get("assetid"),
                platform         = sell_platform,
                price            = current_price,
                price_target     = None,
                url              = sell_url,
                basket_id        = output.get("basket_id"),
                opportunity_name = output.get("opportunity_name", ""),
                reason           = decision["reason"],
                score            = 85,
                float_val        = output.get("float_val"),
                float_norm       = None,
                expires_at       = datetime.utcnow() + timedelta(hours=6),
                valid_until_price = current_price * 0.97,  # valide si > −3%
                created_at       = datetime.utcnow(),
                listing_score    = None,
            )]

        else:
            # Hold — générer une action de surveillance
            hold_days    = decision["hold_days"]
            stop_loss    = decision["stop_loss"]
            review_at    = datetime.utcnow() + timedelta(days=hold_days)

            return [Action(
                type             = ActionType.SELL_HOLD,
                priority         = ActionPriority.LOW,
                market_hash_name = skin_name,
                sale_id          = None,
                assetid          = output.get("assetid"),
                platform         = "skinport",
                price            = current_price,
                price_target     = current_price * (1 + decision["expected_gain"] / 100),
                url              = f"https://skinport.com/item/{output.get('url_slug', '')}",
                basket_id        = output.get("basket_id"),
                opportunity_name = output.get("opportunity_name", ""),
                reason           = (
                    f"Hold {hold_days}j — gain espéré "
                    f"+{decision['expected_gain']}% | "
                    f"Stop-loss : {stop_loss:.2f}€"
                ),
                score            = 40,
                float_val        = output.get("float_val"),
                float_norm       = None,
                expires_at       = review_at,
                valid_until_price = stop_loss,  # vendre si prix descend sous stop-loss
                created_at       = datetime.utcnow(),
                listing_score    = None,
            )]


    # ──────────────────────────────────────────────────────────────────────
    # NOUVELLES OPPORTUNITÉS — si slots disponibles
    # ──────────────────────────────────────────────────────────────────────

    def _new_opportunity_actions(
        self,
        opportunities:  list,
        portfolio:      dict,
        free_slots:     int,
        prices:         dict,
        history:        dict,
        collections_db: dict,
    ) -> list[Action]:
        """
        Pour chaque slot libre, suggère l'opportunité et les inputs exacts
        à acheter en premier pour démarrer le panier.
        """
        actions = []
        # Prendre les meilleures opportunités non encore en portefeuille
        available = [
            o for o in opportunities
            if o["portfolio_status"] == "active"
            and not self._basket_exists(o["id"])
        ][:free_slots]

        for opp in available:
            # Trouver les meilleurs listings pour le PREMIER input à acheter
            # (on commence par l'input le plus liquide pour limiter le risque)
            first_input = self._get_best_first_input(opp, prices, history)
            if not first_input:
                continue

            url = f"https://skinport.com/item/{first_input['url']}/{first_input['sale_id']}"

            actions.append(Action(
                type             = ActionType.BUY_NOW,
                priority         = ActionPriority.NORMAL,
                market_hash_name = first_input["market_hash_name"],
                sale_id          = first_input["sale_id"],
                assetid          = None,
                platform         = "skinport",
                price            = first_input["price"],
                price_target     = None,
                url              = url,
                basket_id        = None,  # panier pas encore ouvert
                opportunity_name = opp["name"],
                reason           = (
                    f"Nouvelle opportunité — Kontract Score {opp['kontract_score']} | "
                    f"ROI {opp['roi']*100:.1f}% | "
                    f"Premier input à acheter (1/10) "
                    f"— score listing {first_input['score']}/100"
                ),
                score            = opp["kontract_score"] * 2,  # pondéré par le score opp
                float_val        = first_input.get("float_val"),
                float_norm       = first_input.get("float_norm"),
                expires_at       = datetime.utcnow() + timedelta(hours=2),
                valid_until_price = first_input["price"] * 1.05,
                created_at       = datetime.utcnow(),
                listing_score    = first_input["score"],
            ))

        return actions


    # ──────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────

    def _best_sell_platform(self, skin_name: str, price: float) -> tuple[str, str]:
        """
        Choisit la meilleure plateforme de vente selon le prix et la liquidité.
        MVP : Skinport uniquement. V2 : + comparaison Steam.
        """
        # Skinport : 3% frais vendeur, interface simple, liquidité internationale
        skinport_url = f"https://skinport.com/sell?search={skin_name.replace(' ', '+')}"
        # Steam : 15% frais, mais 100M+ utilisateurs = meilleure liquidité
        steam_url    = f"https://steamcommunity.com/market/listings/730/{skin_name.replace(' ', '%20')}"

        # Règle simple MVP : Skinport si prix > 10€, Steam sinon (plus de liquidité)
        if price >= 10:
            return "skinport", skinport_url
        return "steam", steam_url

    def _get_best_first_input(self, opp: dict, prices: dict, history: dict) -> dict | None:
        """
        Parmi tous les inputs d'une opportunité, retourne le meilleur listing
        pour commencer le panier (le plus liquide au meilleur prix).
        """
        best = None
        for skin in opp["inputs_required"]:
            listings = self._get_cached_listings(skin["market_hash_name"])
            if not listings:
                continue
            ranked = rank_input_listings(
                listings, target={**skin,
                    "median_price":    prices.get(skin["id"], {}).get("median_price", 999),
                    "max_input_price": opp.get("max_input_price", 999),
                    "stattrak":        opp.get("stattrak", False),
                    "float_crafting":  False,
                    "norm_min": 0, "norm_max": 1, "norm_center": 0.5,
                },
                panier_state={"n_bought": 0, "floats_bought": [], "avg_price": 0},
                top_n=1,
            )
            if ranked["top_listings"]:
                candidate = ranked["top_listings"][0]
                if best is None or candidate["score"] > best["score"]:
                    best = candidate
        return best
```

---

#### Format de sortie — Plan d'action complet

Le plan d'action est généré toutes les 5 minutes et à chaque événement WebSocket. Il est affiché dans le dashboard (page Portefeuille) et poussé sur Telegram.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 PLAN D'ACTION KONTRACT.GG — 14h32 · 3 slots actifs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 URGENT — 2 actions
──────────────────────────────────────────────────
[1] ACHETER MAINTENANT
    FAMAS | Rapid Eye Movement (Minimal Wear)
    Float : 0.1430 (norm 0.893 ✓) | Score listing : 84/100
    Prix : 7.93€ (−17% vs médiane) | Skinport
    Panier : FAMAS REM → AWP Fever Dream FN (3/10 inputs)
    → 🛒 https://skinport.com/item/famas-rapid-eye-movement/6934215
    ⏱️ Expire dans ~2h (vol 24h = 8 ventes/j)

[2] ACHETER MAINTENANT
    FAMAS | Rapid Eye Movement (Minimal Wear)
    Float : 0.1460 (norm 0.920 ✓) | Score listing : 79/100
    Prix : 7.95€ (−17% vs médiane) | Skinport
    Panier : idem — 4/10 après achat
    → 🛒 https://skinport.com/item/famas-rapid-eye-movement/6934221

🟡 CE SOIR — 3 actions
──────────────────────────────────────────────────
[3] SURVEILLER — ACHETER SI PRIX ≤ 8.10€
    FAMAS | Rapid Eye Movement (Minimal Wear)
    Prix actuel : 8.39€ (légèrement au-dessus de la cible)
    Surveiller : https://skinport.com/market/730?item=famas-rapid-eye-movement
    Panier : FAMAS REM → AWP Fever Dream FN (5/10 après les 2 achats ci-dessus)

[4] VENDRE MAINTENANT
    AWP | Fever Dream (Field-Tested) — float 0.247
    Prix actuel : 22.40€ | Momentum : 📈 +0.52 mais slot libre disponible
    → Seuil hold non atteint (gain espéré +7.5% < seuil +10.8%)
    → 💰 https://skinport.com/sell (chercher "AWP Fever Dream FT")

[5] ATTENDRE — ne pas acheter encore
    AK-47 | Redline (Field-Tested) — inputs panier AK → Asiimov
    Recipe velocity détectée : inputs +6% en 24h
    → Attendre retour à la normale (estimé 24–48h)
    → Surveiller : https://skinport.com/market/730?item=ak47-redline

🟢 CETTE SEMAINE — 1 action
──────────────────────────────────────────────────
[6] NOUVELLE OPPORTUNITÉ — 1 slot disponible
    M4A4 | Howl input → AWP | Dragon Lore BS
    Kontract Score : 18.9 | ROI : +15% | Pool : 2 outcomes
    Premier input à acheter :
    M4A4 | Howl (Field-Tested) float=0.289 | Score : 77/100
    Prix : 12.40€ | Skinport
    → 🛒 https://skinport.com/item/m4a4-howl/7234156
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

#### Alerte Telegram condensée (pour les actions urgentes uniquement)

```
🔴 ACTION URGENTE — KONTRACT.GG

[ACHETER] FAMAS | REM MW
Float 0.143 · Score 84/100 · 7.93€ (−17%)
Panier : Fever Dream FN · Input 3/10

→ 🛒 skinport.com/item/famas-rapid-eye-movement/6934215

[ACHETER] même skin — listing suivant
Float 0.146 · Score 79/100 · 7.95€
→ 🛒 skinport.com/item/famas-rapid-eye-movement/6934221
```

---

#### Cas spécial — Stratégie avec fillers : liens exacts pour chaque filler

Quand la stratégie "fillers" est sélectionnée, le plan d'action donne les **7 inputs collection cible + 3 fillers avec liens directs** vers chaque item optimal.

```python
def _build_filler_action_plan(
    opp:     dict,   # opportunité avec stratégie "fillers"
    prices:  dict,
    history: dict,
) -> list[Action]:
    """
    Pour une stratégie fillers 7+3, génère :
    - 7 actions d'achat pour les inputs collection cible
    - 3 actions d'achat pour les fillers optimaux
    Chaque action pointe vers le listing exact le moins cher
    avec le float le plus large possible (post-update oct 2025).
    """
    actions = []

    # ── 7 inputs collection cible ─────────────────────────────────────
    for i, skin in enumerate(opp["inputs_cible"][:7]):
        listings = get_cached_listings(skin["market_hash_name"])
        ranked   = rank_input_listings(listings, target=skin,
                       panier_state={"n_bought": i, "floats_bought": [], "avg_price": 0},
                       top_n=1)
        if ranked["top_listings"]:
            best = ranked["top_listings"][0]
            actions.append(Action(
                type             = ActionType.BUY_NOW,
                market_hash_name = best["market_hash_name"],
                sale_id          = best["sale_id"],
                url              = f"https://skinport.com/item/{best['url']}/{best['sale_id']}",
                price            = best["price"],
                reason           = f"Input {i+1}/7 (collection cible)",
                # ...
            ))

    # ── 3 fillers optimaux ───────────────────────────────────────────
    # Critères post-oct 2025 : moins cher + float range le plus large
    filler_candidates = opp["filler_collection"]["skins"]
    fillers_sorted    = sorted(
        filler_candidates,
        key=lambda s: (prices.get(s["id"], {}).get("min_price", 999),
                       -(s["float_max"] - s["float_min"]))  # prix ASC, range DESC
    )[:3]

    for j, filler in enumerate(fillers_sorted):
        filler_listings = get_cached_listings(filler["market_hash_name"])
        filler_ranked   = rank_input_listings(
            filler_listings,
            target={
                **filler,
                "float_crafting": False,  # float neutre pour fillers
                "norm_min": 0, "norm_max": 1, "norm_center": 0.5,
                "stattrak": opp["stattrak"],
                "median_price": prices.get(filler["id"], {}).get("median_price", 0),
                "max_input_price": opp.get("max_filler_price", 5.0),
            },
            panier_state={"n_bought": 7+j, "floats_bought": [], "avg_price": 0},
            top_n=1,
        )
        if filler_ranked["top_listings"]:
            best_filler = filler_ranked["top_listings"][0]
            actions.append(Action(
                type             = ActionType.BUY_NOW,
                market_hash_name = best_filler["market_hash_name"],
                sale_id          = best_filler["sale_id"],
                url              = (
                    f"https://skinport.com/item/"
                    f"{best_filler['url']}/{best_filler['sale_id']}"
                ),
                price            = best_filler["price"],
                float_val        = best_filler.get("float_val"),
                reason           = (
                    f"Filler {j+1}/3 — {filler['name']} "
                    f"float range {filler['float_min']:.2f}–{filler['float_max']:.2f} "
                    f"(range={filler['float_max']-filler['float_min']:.2f}) "
                    f"| Prix : {best_filler['price']:.2f}€"
                ),
                # ...
            ))

    return actions
```

**Exemple de sortie pour une stratégie fillers :**

```
PLAN D'ACHAT — FAMAS REM → AWP Fever Dream FN (stratégie fillers 7+3)
Coût estimé total : 63.51€ | ROI estimé : +24%

INPUTS COLLECTION CIBLE (7×)
[1] FAMAS | REM MW  float=0.143  7.93€  score 84  → skinport.com/item/.../6934215
[2] FAMAS | REM MW  float=0.146  7.95€  score 79  → skinport.com/item/.../6934221
[3] FAMAS | REM MW  float=0.137  8.00€  score 71  → skinport.com/item/.../6934301
[4] FAMAS | REM MW  float=0.144  8.00€  score 69  → skinport.com/item/.../6934318
[5] FAMAS | REM MW  float=0.139  8.32€  score 65  → skinport.com/item/.../6934422
[6] FAMAS | REM MW  float=0.125  8.41€  score 63  → skinport.com/item/.../6934509
[7] FAMAS | REM MW  float=0.132  8.39€  score 61  → skinport.com/item/.../6934601

FILLERS (3×) — collection Genesis, float range max
[8] MP5-SD | Focus (MW)   float=0.112  0.84€  range 0.00–1.00  → skinport.com/item/.../7012301
[9] MP5-SD | Focus (MW)   float=0.098  0.86€  range 0.00–1.00  → skinport.com/item/.../7012389
[10] MP5-SD | Focus (MW)  float=0.124  0.89€  range 0.00–1.00  → skinport.com/item/.../7012412

Float output prédit : 0.71 → Battle-Scarred
(Pour viser FT sur l'output, utiliser la stratégie pure sans fillers)
```

---

#### Schéma BDD — table actions

```sql
action_plans :
    id               UUID PRIMARY KEY,
    user_id          UUID,
    generated_at     TIMESTAMP,
    cycle_id         INTEGER  -- numéro du cycle 5min

actions :
    id               UUID PRIMARY KEY,
    plan_id          UUID REFERENCES action_plans(id),
    user_id          UUID,
    type             TEXT,    -- buy_now | buy_watch | sell_now | sell_hold | execute | abandon
    priority         TEXT,    -- urgent | high | normal | low
    market_hash_name TEXT,
    sale_id          TEXT,    -- NULL si pas un listing spécifique
    assetid          TEXT,    -- NULL si pas encore en inventaire
    platform         TEXT,
    price            DECIMAL(10,2),
    price_target     DECIMAL(10,2),  -- NULL sauf buy_watch
    url              TEXT,
    basket_id        UUID,
    opportunity_name TEXT,
    reason           TEXT,
    score            DECIMAL(6,2),
    float_val        DECIMAL(10,8),
    listing_score    DECIMAL(5,1),
    expires_at       TIMESTAMP,
    valid_until_price DECIMAL(10,2),
    -- Lifecycle
    status           TEXT,    -- "pending" | "executed" | "expired" | "cancelled"
    executed_at      TIMESTAMP,
    created_at       TIMESTAMP
```

---


### 4.15 Module — Fonctions utilitaires (stubs)

Ces fonctions sont appelées par plusieurs modules. Elles sont regroupées ici pour éviter la duplication dans le code.

```python
# ── helpers/ev.py ─────────────────────────────────────────────────────────────

async def calculate_ev(
    inputs: list,
    output_target: dict,
    prices: dict,
    frais_vente: float = FEES["skinport"]["seller"],
) -> tuple[float, float]:
    """Calcule (ev_nette, roi) pour une liste d'inputs et un output cible."""
    prob = 1 / len(output_target["outputs"])  # simplifié — réel dans ev_calculator.py
    ev_brute = sum(prob * get_sell_price(o, prices)[0] for o in output_target["outputs"])
    cout = sum(get_input_price(prices.get(s["id"], {})) for s in inputs)
    ev_nette = ev_brute * (1 - frais_vente) - cout
    roi = ev_nette / cout if cout > 0 else 0
    return ev_nette, roi

async def get_current_sell_price(market_hash_name: str) -> float:
    """Prix de vente actuel sur Skinport (min_price ou médiane si min aberrant)."""
    items = await skinport_cache.get(market_hash_name)
    return get_input_price(items or {}) or 0.0

def get_current_min_price(item: dict) -> float:
    """Prix minimum actuel pour un item (depuis le cache Skinport)."""
    return skinport_cache.get_sync(item["market_hash_name"], {}).get("min_price", 0.0)

def get_output_wear_from_float(float_val: float, output_skin: dict) -> str:
    """Détermine la condition de wear depuis le float et les bornes du skin."""
    f_min = output_skin.get("float_min", 0.0)
    f_max = output_skin.get("float_max", 1.0)
    # Normaliser sur [0,1] via les bornes réelles
    if f_max <= f_min: return "Unknown"
    thresholds = [("Factory New", 0.07), ("Minimal Wear", 0.15),
                  ("Field-Tested", 0.38), ("Well-Worn", 0.45)]
    for wear, cap in thresholds:
        if float_val < f_min + cap * (f_max - f_min):
            return wear
    return "Battle-Scarred"

def get_days_since_update() -> int:
    """Retourne le nombre de jours depuis la dernière MAJ Valve connue."""
    # En MVP : valeur statique mise à jour manuellement après chaque update
    # En V2 : scrape https://store.steampowered.com/news/app/730
    from datetime import date
    LAST_KNOWN_UPDATE = date(2026, 1, 24)  # mettre à jour manuellement
    return (date.today() - LAST_KNOWN_UPDATE).days

# ── helpers/inventory.py ──────────────────────────────────────────────────────

async def recalculate_opportunity(opp: dict, prices: dict) -> dict:
    """Recalcule EV, ROI et Kontract Score avec les prix frais."""
    ev_nette, roi = await calculate_ev(opp["inputs"], opp, prices)
    momentum = PriceSignalEngine().compute_output_momentum(
        opp["output_skin"], opp["collection"], 
        prices.get("history", {}).get(opp["output_name"], {}),
        prices.get(opp["output_name"], {}), []
    )
    score, _ = calculate_kontract_score({
        **opp, "ev_nette": ev_nette,
        "output_momentum_score": momentum["momentum_score"],
    })
    return {**opp, "ev_nette": ev_nette, "roi": roi, "kontract_score": score}

async def create_basket(opp: dict, user: dict) -> dict:
    """Crée un nouveau panier en BDD et retourne l'objet basket."""
    basket_id = await db.insert_basket({
        "user_id": user["id"], "opportunity_id": opp["id"],
        "n_required": 5 if opp.get("is_covert") else 10,
        "status": "in_progress",
    })
    return {"id": basket_id, "opportunity": opp, "user": user,
            "state": PanierState(basket_id, user["id"])}

def _get_cached_listings(market_hash_name: str) -> list:
    """Récupère les listings en cache (WebSocket feed + TTL 5min)."""
    return websocket_cache.get(market_hash_name, [])

def get_peer_skins(collection: dict, exclude_skin: dict) -> list:
    """Retourne les autres skins de la même collection (pour corrélation momentum)."""
    return [s for s in collection.get("contains", [])
            if s["id"] != exclude_skin.get("id")]

async def get_detected_output(basket_id: str) -> dict:
    """Récupère l'output auto-détecté depuis la BDD (table trade_up_baskets)."""
    return await db.get_basket_field(basket_id,
        ["output_detected", "output_float", "output_wear"])

# ── helpers/notifications.py ─────────────────────────────────────────────────

async def notify_basket_ready(basket: dict):
    """Alerte Telegram : panier complet, prêt à exécuter."""
    opp = basket["opportunity"]
    msg = (
        f"✅ Panier complet — {opp['name']}\n"
        f"10/10 inputs dans l'inventaire ✓\n"
        f"Float output prédit : {basket['state'].predict_output_float(opp['output_skin']):.4f}\n"
        f"EV estimée : {opp['ev_nette']:+.2f}€\n"
        f"→ Ouvrir CS2 → Inventaire → Contrats"
    )
    await telegram_bot.send(basket["user"]["id"], msg)

async def notify_basket_opened(basket: dict):
    """Alerte Telegram : nouveau panier ouvert."""
    opp = basket["opportunity"]
    await telegram_bot.send(basket["user"]["id"],
        f"📂 Nouveau panier ouvert — {opp['name']}\n"
        f"Kontract Score : {opp['kontract_score']} | ROI : {opp['roi']*100:.1f}%\n"
        f"Premier achat recommandé dans le Plan d'action."
    )

async def notify_abandon_recommendation(basket: dict, reason: str):
    """Alerte Telegram : abandon recommandé avec calcul perte."""
    await telegram_bot.send(basket["user"]["id"],
        f"⚠️ Abandon recommandé — {basket['opportunity']['name']}\n"
        f"Raison : {reason}\n"
        f"→ Voir le Plan d'action pour les liens de revente."
    )

async def schedule_hold_monitoring(basket_id: str, hold_days: int, engine: "OutputSellEngine"):
    """Planifie la réévaluation toutes les 5min pendant le hold."""
    # APScheduler job temporaire — supprimé automatiquement après hold_days
    scheduler.add_job(
        func=lambda: check_hold_and_notify(basket_id, engine),
        trigger="interval", minutes=5,
        id=f"hold_{basket_id}",
        end_date=datetime.utcnow() + timedelta(days=hold_days),
    )

# ── helpers/selectors.py ─────────────────────────────────────────────────────

def select_cheapest(candidates: list, n: int = 10) -> list:
    """Sélectionne les N skins les moins chers parmi les candidats."""
    return sorted(candidates, key=lambda s: s.get("min_price", 999))[:n]

def select_cheapest_low_float(candidates: list, n: int = 10,
                               target_avg_norm: float = 0.05) -> list:
    """
    Sélectionne les N skins avec le meilleur compromis prix/float bas.
    Utilisé pour le float crafting Factory New.
    """
    scored = []
    for c in candidates:
        price = c.get("min_price", 999)
        fnorm = c.get("float_norm", 0.5)
        # Score : favorise les floats proches de target ET les prix bas
        float_dist = abs(fnorm - target_avg_norm)
        score = price * (1 + float_dist * 5)  # pénaliser les floats éloignés
        scored.append((score, c))
    return [c for _, c in sorted(scored)[:n]]
```


### 4.16 Stratégies non encore exploitées

#### Stratégie 1 — Reverse finder (output → inputs optimaux)

Déjà mentionné dans la roadmap S4 mais non spécifié. Le sens inverse : l'utilisateur choisit un output désirable (ex: AWP Dragon Lore FN) et le moteur identifie automatiquement les inputs permettant de l'obtenir au meilleur ROI.

```python
def reverse_find_inputs(
    target_output: dict,
    prices:         dict,
    collections_db: dict,
    constraints:    dict,   # budget, float_target, stattrak, etc.
) -> list[dict]:
    """
    Pour un output cible, trouve toutes les combinaisons d'inputs
    permettant de l'obtenir, triées par ROI décroissant.
    """
    results = []
    # Trouver toutes les collections dont cet output est membre
    for collection in collections_db.values():
        for skin in collection["contains"]:
            if skin["rarity"]["id"] == target_output["rarity"]["id"]:
                # Ce skin peut être un input pour produire cet output
                strategy_pure  = calc_pure_strategy(skin, target_output, prices, collection)
                strategy_filler = calc_filler_strategy(skin, target_output, prices, collection)
                results += [strategy_pure, strategy_filler]

    return sorted(
        [r for r in results if r["roi"] >= constraints.get("min_roi", 0.05)],
        key=lambda x: -x["kontract_score"]
    )
```

---

#### Stratégie 2 — Covert → Couteaux/Gants (5 inputs)

Spécifique à la règle post-octobre 2025. Seulement 5 inputs au lieu de 10. Le budget est réduit de moitié mais les outputs (couteaux, gants) peuvent valoir 5–50× le coût des inputs.

```python
COVERT_STRATEGY = {
    "n_inputs":           5,         # règle Valve post-oct 2025
    "rarity_required":    "rarity_ancient_weapon",   # Covert uniquement
    "output_tier":        "gold",    # couteaux et gants
    "min_input_price":    20.0,      # les Covert coûtent généralement 20–200€
    "leverage_ratio":     "10–50×",  # output vaut 10 à 50× le coût inputs
    "risk":               "très élevé — pool d'outputs très large",
    "recommended_for":    "capital > 500€, appétit risque élevé",
}

def calculate_covert_ev(inputs: list, prices: dict) -> dict:
    """
    EV spécifique aux trade-ups Covert → Gold.
    Pool d'outputs = tous les couteaux + gants disponibles.
    Pondération identique (1/nb_outputs).
    """
    all_gold = get_all_gold_items(prices)  # couteaux + gants
    prob_per  = 1 / len(all_gold)
    ev_brute  = sum(prob_per * prices.get(g["market_hash_name"], {}).get("median_price", 0)
                   for g in all_gold)
    cout      = sum(get_input_price(prices.get(s["id"], {})) for s in inputs[:5])
    return {"ev_nette": ev_brute * 0.97 - cout, "roi": (ev_brute * 0.97 - cout) / cout}
```

---

#### Stratégie 3 — StatTrak EV différenciée

Un trade-up StatTrak produit un output StatTrak, qui vaut généralement 20–40% de plus. Mais les inputs StatTrak coûtent aussi plus cher. Le calcul doit être fait séparément car les marchés sont différents.

```python
def calculate_stattrak_premium_ev(
    inputs_st: list,     # inputs StatTrak
    output_st: dict,     # output StatTrak cible
    inputs_nst: list,    # inputs non-StatTrak (référence)
    output_nst: dict,    # output non-StatTrak (référence)
    prices: dict,
) -> dict:
    """
    Compare EV ST vs EV non-ST et calcule si le premium StatTrak
    justifie le surcoût des inputs.
    """
    ev_st,  roi_st  = calculate_ev(inputs_st,  output_st,  prices)
    ev_nst, roi_nst = calculate_ev(inputs_nst, output_nst, prices)

    cout_st  = sum(get_input_price(prices.get(s["id"], {})) for s in inputs_st)
    cout_nst = sum(get_input_price(prices.get(s["id"], {})) for s in inputs_nst)
    st_premium_cost   = cout_st  - cout_nst
    st_premium_output = ev_st    - ev_nst

    return {
        "ev_nette_st":          ev_st,
        "ev_nette_nst":         ev_nst,
        "roi_st":               roi_st,
        "roi_nst":              roi_nst,
        "st_worth_it":          roi_st > roi_nst,
        "premium_cost_pct":     st_premium_cost  / cout_nst  if cout_nst else 0,
        "premium_output_pct":   st_premium_output / ev_nst   if ev_nst   else 0,
        "recommendation": "StatTrak" if roi_st > roi_nst else "Non-StatTrak",
    }
```

---

#### Stratégie 4 — Liquidity decay modeling (impact prix achat 10× même skin)

Acheter 10 unités du même skin fait monter les prix. La spec ignore actuellement cet effet. Pour les skins peu liquides (< 50 ventes/7j), acheter 10 unités consomme une fraction significative du carnet.

```python
def estimate_execution_cost(
    skin_name:   str,
    n_needed:    int,
    prices:      dict,
    history:     dict,
) -> dict:
    """
    Estime le coût réel d'achat de N unités en tenant compte
    de la pression prix (on ne peut pas tout acheter au min_price).
    """
    min_price    = prices.get(skin_name, {}).get("min_price", 0)
    median_price = prices.get(skin_name, {}).get("median_price", 0)
    quantity     = prices.get(skin_name, {}).get("quantity", 0)
    vol_7d       = history.get(skin_name, {}).get("last_7_days", {}).get("volume", 1)

    # Si on a besoin de plus de 20% du stock disponible → impact prix
    demand_ratio = n_needed / max(quantity, 1)

    if demand_ratio < 0.20:
        # Peu d'impact — utiliser min_price
        return {"avg_cost": min_price, "price_impact": 0, "risk": "low"}
    elif demand_ratio < 0.50:
        # Impact modéré — interpoler entre min et médiane
        avg_cost = min_price + (median_price - min_price) * demand_ratio
        return {"avg_cost": avg_cost, "price_impact": avg_cost - min_price, "risk": "medium"}
    else:
        # Impact fort — utiliser médiane + 10%
        avg_cost = median_price * 1.10
        return {"avg_cost": avg_cost, "price_impact": avg_cost - min_price, "risk": "high",
                "warning": f"Acheter {n_needed} unités représente {demand_ratio*100:.0f}% du stock"}
```

---

#### Stratégie 5 — Time-to-fill estimation

Combien de temps pour compléter un panier ? Nécessaire pour calculer le cycle_days réel utilisé dans l'OutputSellEngine.

```python
def estimate_time_to_fill(
    inputs_required: list,
    history:         dict,
    n_needed:        int = 10,
) -> dict:
    """
    Estime la durée pour compléter un panier, en jours.
    Basé sur le volume de ventes quotidien de chaque input.
    """
    bottleneck_days = 0
    bottleneck_skin = None

    for skin in inputs_required:
        h        = history.get(skin["market_hash_name"], {})
        vol_24h  = h.get("last_24_hours", {}).get("volume", 0) or 0.1
        days_for_skin = n_needed / vol_24h  # jours pour trouver N unités
        if days_for_skin > bottleneck_days:
            bottleneck_days = days_for_skin
            bottleneck_skin = skin["name"]

    return {
        "estimated_days":  round(bottleneck_days, 1),
        "bottleneck_skin": bottleneck_skin,
        "cycle_days_total": round(bottleneck_days + 0.5, 1),  # +0.5j exécution
        "confidence":       "high" if bottleneck_days < 2 else
                            "medium" if bottleneck_days < 7 else "low",
    }
```

Intégré dans `calculate_kontract_score` via `cycle_days` pour l'OutputSellEngine, et affiché dans le panneau de détail Scanner.

---

#### Stratégie 6 — Backtesting module

Valide la précision du moteur EV sur des données historiques. Indispensable pour calibrer les paramètres et démontrer la valeur aux utilisateurs.

```python
def backtest_strategy(
    historical_prices: list,   # prix historiques par date
    historical_trades: list,   # trades réels exécutés (pnl_records)
    strategy_config:   dict,
) -> dict:
    """
    Rejoue la stratégie sur les prix historiques et compare
    les résultats simulés aux résultats réels.
    """
    simulated_pnl = []
    for date_slice in historical_prices:
        opportunities = scan_all(date_slice["prices"], date_slice["history"])
        top_10 = sorted(opportunities, key=lambda x: -x["kontract_score"])[:10]
        for opp in top_10:
            future_price = get_future_price(opp["output_name"],
                                            date_slice["date"],
                                            days_ahead=5,
                                            historical_prices=historical_prices)
            if future_price:
                simulated_pnl.append(future_price - opp["cout_ajuste"])

    return {
        "simulated_roi_avg":  sum(simulated_pnl) / len(simulated_pnl),
        "win_rate":           sum(1 for p in simulated_pnl if p > 0) / len(simulated_pnl),
        "vs_real_pnl":        compare_with_real(simulated_pnl, historical_trades),
        "ev_calibration":     "ok" if abs(sum(simulated_pnl)/len(simulated_pnl)
                                         - strategy_config["expected_roi"]) < 0.05 else "drift",
    }
```

> Scope V2 — nécessite 3+ mois de données historiques accumulées en interne.

---

### 4.17 Module LLM — Intelligence artificielle dans Kontract.gg

#### Pourquoi un LLM ? Cas d'usage identifiés

Le LLM n'est pas utile pour les calculs quantitatifs (l'EV, le score, les probabilités sont mieux faits par du code déterministe). Il est utile pour **les tâches qui nécessitent du langage naturel, du contexte et du raisonnement sur des données non structurées**.

| Cas d'usage | Valeur | Faisabilité MVP |
|------------|--------|----------------|
| Analyse des patch notes Valve → impact prix | ⭐⭐⭐⭐⭐ | ✓ |
| Résumé narratif du plan d'action | ⭐⭐⭐ | ✓ |
| Explication pédagogique d'une opportunité | ⭐⭐⭐⭐ | ✓ |
| Détection d'anomalies textuelles (forums, Discord) | ⭐⭐⭐ | V2 |
| Assistant de configuration (onboarding) | ⭐⭐ | V2 |
| Prédiction de MAJ Valve (signal faible) | ⭐⭐⭐⭐ | V2 |

---

#### LLM Call 1 — Analyse de patch notes Valve

Le signal de risque Valve le plus précoce possible : analyser les patch notes le jour même et estimer l'impact potentiel sur les prix des skins.

```python
async def analyze_valve_patch(patch_notes: str) -> dict:
    """
    Analyse les patch notes Valve avec un LLM pour détecter
    les changements susceptibles d'impacter les prix des skins.
    Appelé dès qu'une nouvelle MAJ est détectée (monitoring updates.valve.com).
    """
    response = await fetch("https://api.anthropic.com/v1/messages", {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1000,
        "system": (
            "You are an expert CS2 skin market analyst. "
            "Analyze CS2 patch notes and identify any changes that could affect skin prices. "
            "Respond ONLY in JSON with this exact schema: "
            '{"risk_level": "low|medium|high|critical", ' +
            '"affected_categories": ["covert", "knives", "gloves", ...], ' +
            '"price_direction": "up|down|mixed|unknown", ' +
            '"trade_up_impact": "none|minor|major|game_changing", ' +
            '"summary": "2-sentence explanation", ' +
            '"recommended_action": "hold|sell|buy|pause_trading"}' +
            " No preamble, no markdown, pure JSON."
        ),
        "messages": [{"role": "user", "content": f"Patch notes to analyze:\n{patch_notes}"}],
    })

    text = response["content"][0]["text"]
    result = json.loads(text)

    # Si impact élevé → alerte immédiate à tous les utilisateurs
    if result["risk_level"] in ("high", "critical"):
        await alert_all_users_valve_update(result)

    return result
```

**Exemple de réponse pour la MAJ octobre 2025 :**
```json
{
  "risk_level": "critical",
  "affected_categories": ["knives", "gloves", "covert"],
  "price_direction": "mixed",
  "trade_up_impact": "game_changing",
  "summary": "Trade-up contracts now allow 5 Covert skins to produce knives/gloves. This massively increases knife supply and crashes their prices, while spiking Covert skin demand.",
  "recommended_action": "sell"
}
```

---

#### LLM Call 2 — Explication pédagogique d'une opportunité

Pour les nouveaux utilisateurs, l'EV et le Kontract Score sont des concepts abstraits. Un LLM peut générer une explication claire, en français, adaptée au niveau de l'utilisateur.

```python
async def explain_opportunity(opportunity: dict, user_level: str = "beginner") -> str:
    """
    Génère une explication claire de pourquoi cette opportunité est intéressante.
    user_level: "beginner" | "intermediate" | "expert"
    """
    opp_data = {
        "name":          opportunity["name"],
        "roi":           f"{opportunity['roi']*100:.1f}%",
        "ev_nette":      f"{opportunity['ev_nette']:.2f}€",
        "pool_size":     opportunity["pool_size"],
        "momentum":      opportunity.get("output_momentum_verdict", "neutral"),
        "win_prob":      f"{opportunity.get('win_prob', 0)*100:.0f}%",
        "floor_ratio":   f"{opportunity.get('floor_ratio', 0)*100:.0f}%",
        "collection_inactive": opportunity.get("collection_inactive", False),
    }
    level_instruction = {
        "beginner":     "Explain simply in 3-4 sentences as if to someone who just started trading CS2 skins. Avoid jargon.",
        "intermediate": "Explain in 4-5 sentences, mentioning EV and ROI naturally.",
        "expert":       "Be concise, mention Sharpe ratio, floor ratio, momentum. Max 3 sentences.",
    }[user_level]

    response = await fetch("https://api.anthropic.com/v1/messages", {
        "model": "claude-sonnet-4-6",
        "max_tokens": 300,
        "messages": [{
            "role": "user",
            "content": (
                f"Explain this CS2 trade-up opportunity in French: {json.dumps(opp_data)}. "
                f"{level_instruction} "
                f"Focus on why it is a good opportunity RIGHT NOW."
            )
        }],
    })
    return response["content"][0]["text"]
```

---

#### LLM Call 3 — Détection de signaux faibles sur forums/Discord (V2)

Les forums communautaires (r/csgomarketforum, Discord trading servers) contiennent souvent des signaux avant qu'ils ne se reflètent dans les prix. Un LLM peut monitorer ces sources et identifier les opportunités mentionnées.

```python
async def analyze_community_signal(posts: list[str], skin_names: list[str]) -> dict:
    """
    Analyse des posts communautaires pour détecter les mentions
    bullish/bearish sur des skins spécifiques.
    Appelé toutes les heures sur un sample de posts Reddit/Discord.
    """
    response = await fetch("https://api.anthropic.com/v1/messages", {
        "model": "claude-sonnet-4-6",
        "max_tokens": 500,
        "system": (
            "You analyze CS2 trading community posts to find bullish/bearish signals. "
            "Respond in JSON: {"signals": [{"skin": str, "sentiment": "bullish|bearish|neutral", "
            ""confidence": 0-1, "reason": str}]}"
        ),
        "messages": [{
            "role": "user",
            "content": (
                f"Skins to monitor: {skin_names}\n"
                f"Community posts:\n" + "\n---\n".join(posts[:20])
            )
        }],
    })
    return json.loads(response["content"][0]["text"])
```

---

#### LLM Call 4 — Assistant de configuration (onboarding)

À la première connexion, au lieu d'un formulaire complexe, un LLM guide l'utilisateur par conversation pour configurer son profil optimal.

```python
ONBOARDING_SYSTEM = """
You are Kontract, an AI assistant helping CS2 skin traders configure their trade-up strategy.
Ask 3-4 natural questions to determine:
1. Their budget (€)
2. Their risk appetite (conservative/balanced/aggressive)
3. Their available time per day (few minutes / 1 hour / several hours)
4. Whether they use BUFF163 or Skinport only

Based on answers, recommend a PORTFOLIO_CONFIG in JSON.
Keep conversation friendly and in the user's language.
"""

async def onboarding_conversation(messages: list[dict]) -> dict:
    response = await fetch("https://api.anthropic.com/v1/messages", {
        "model": "claude-sonnet-4-6",
        "max_tokens": 500,
        "system": ONBOARDING_SYSTEM,
        "messages": messages,
    })
    text = response["content"][0]["text"]
    # Si la réponse contient un JSON de config → configuration terminée
    try:
        config = json.loads(text.split("```json")[-1].split("```")[0])
        return {"status": "complete", "config": config, "message": text}
    except:
        return {"status": "continue", "message": text}
```

---

#### LLM Call 5 — Résumé narratif du plan d'action quotidien

Plutôt qu'une liste brute d'actions, un LLM génère un briefing matinal en 3-4 phrases qui contextualise ce qu'il faut faire aujourd'hui.

```python
async def generate_daily_briefing(
    actions:      list[dict],
    portfolio:    dict,
    market_ctx:   dict,
) -> str:
    """
    Génère un résumé narratif du plan d'action pour la journée.
    Envoyé via Telegram à 9h chaque matin.
    """
    summary = {
        "urgent_actions":   len([a for a in actions if a["priority"] == "urgent"]),
        "active_baskets":   len(portfolio["active_baskets"]),
        "total_invested":   portfolio["capital_engaged"],
        "pending_outputs":  len(portfolio.get("pending_outputs", [])),
        "market_momentum":  market_ctx.get("global_trend", "neutral"),
        "seasonal_phase":   market_ctx.get("seasonal_phase", "neutral"),
        "days_since_update": market_ctx.get("days_since_valve_update", 30),
    }

    response = await fetch("https://api.anthropic.com/v1/messages", {
        "model": "claude-sonnet-4-6",
        "max_tokens": 200,
        "messages": [{
            "role": "user",
            "content": (
                f"Write a 3-sentence morning briefing in French for a CS2 trader: "
                f"{json.dumps(summary)}. "
                f"Be direct, mention the most important action first, "
                f"and note any risk or opportunity in the market context."
            )
        }],
    })
    return response["content"][0]["text"]
```

---

#### Coûts et rate limits LLM

| Call | Fréquence | Tokens ≈ | Coût estimé/mois |
|------|-----------|---------|-----------------|
| Patch notes analyzer | Lors de chaque update Valve | 2 000 | < 0.50€ |
| Opportunity explainer | À la demande (clic utilisateur) | 500 | ~5€ / 1000 clics |
| Community signals | 1×/heure | 5 000 | ~15€/mois |
| Onboarding conversation | 1×/nouvel utilisateur | 3 000 | < 0.10€/user |
| Daily briefing | 1×/jour/utilisateur | 1 000 | ~1€/100 users/mois |

**Total estimé pour 100 utilisateurs actifs :** < 25€/mois — négligeable vs le MRR de 900€.

> **Modèle recommandé** : `claude-sonnet-4-6` — meilleur rapport qualité/coût pour ces tâches structurées. Les calls LLM ne sont jamais sur le chemin critique de l'EV (qui reste 100% déterministe).

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
| LLM (V1) | Anthropic claude-sonnet-4-6 | — | 5 LLM calls : patch analyzer, explainer, onboarding, briefing |

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
│   ├── kontract_score.py    # Kontract Score v4 (Sharpe ratio, floor, hold discount, momentum)
│   └── filters.py           # Hard filters + score hybride listings (inputs)
├── basket/
│   ├── panier_state.py      # Classe PanierState — suivi panier en cours
│   ├── output_detector.py   # OutputDetector — snapshot + polling inventaire
│   └── abandon.py           # should_abandon_basket() — logique d'abandon
├── portfolio/
│   ├── portfolio_engine.py  # PortfolioEngine — cycle 5min, conflits, slots
│   └── buy_alert_engine.py  # BuyAlertEngine — WebSocket → alertes < 500ms
├── pnl/
│   ├── tracker.py           # record_execution(), verify_float_prediction()
│   └── sell_engine.py       # OutputSellEngine — décision hold/sell + stop-loss
├── recommender/
│   ├── action_recommender.py # ActionRecommender — plan d'actions complet
│   ├── buy_planner.py        # _buy_actions(), _new_opportunity_actions()
│   └── sell_planner.py       # _sell_actions(), _best_sell_platform()
├── alerts/
│   ├── telegram_bot.py      # Bot Telegram + commandes /config /panier /executed
│   └── notifier.py          # Match opportunités ↔ profils utilisateurs
├── ui/
│   ├── pages/
│   │   ├── plan_action.py   # Page 0 — Plan d'action (accueil) + vues détail
│   │   ├── scanner.py       # Page 1 — Scanner + filtres + détail opportunité
│   │   ├── portefeuille.py  # Page 2 — Paniers actifs + listings recommandés
│   │   ├── calculateur.py   # Page 3 — Calculateur manuel + float crafting
│   │   └── pnl.py           # Page 4 — Historique trades + stats + courbe P&L
│   └── dashboard.py         # Streamlit app root + sidebar navigation (5 pages)
├── helpers/
│   ├── ev.py               # calculate_ev(), get_current_sell_price(), get_current_min_price()
│   ├── inventory.py        # recalculate_opportunity(), create_basket(), get_peer_skins()
│   ├── notifications.py    # notify_basket_ready/opened/abandon, schedule_hold_monitoring
│   └── selectors.py        # select_cheapest(), select_cheapest_low_float()
├── llm/
│   ├── patch_analyzer.py   # LLM Call 1 — analyse patch notes Valve
│   ├── explainer.py        # LLM Call 2 — explication pédagogique opportunité
│   ├── community.py        # LLM Call 3 — signaux forums/Discord (V2)
│   ├── onboarding.py       # LLM Call 4 — configuration guidée par LLM
│   └── briefing.py         # LLM Call 5 — résumé narratif quotidien
└── backtesting/
    └── backtest.py         # backtest_strategy() — validation sur données historiques (V2)
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
| **V1 — Lancement** | 3 semaines | Auth Supabase+Steam + OAuth Steam, Stripe Free/Trader/Pro, sync inventaire Steam automatique, OutputDetector + polling, CSFloat float auto, P&L Tracker + page P&L, should_abandon_basket() opérationnel, vérification précision float, OutputSellEngine 4.11 (décision hold/sell + stop-loss monitoring) | + Steam Inventory API + CSFloat | Semaine 6 |
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
- WebSocket Skinport en temps réel pour les alertes d'achat, ActionRecommender 4.13 (plan d'actions Telegram avec items exacts + liens directs) (< 500ms)
- Kontract Score v4 (Sharpe ratio — suppression double-comptage + momentum multiplier)
- 8 hard filters + score hybride 4 dimensions pour chaque listing
- PanierState avec sync inventaire Steam et calcul dynamique du float marginal requis
- OutputDetector : détection automatique de l'output via comparaison d'inventaire
- P&L Tracker avec vérification de la précision de la formule de float
- OutputSellEngine : décision hold vs vente immédiate basée sur la vélocité du capital et le momentum — stop-loss automatique pendant le hold

| Coût données MVP | Délai MVP | Modules | Rate limit Skinport | Dépendances critiques |
|-----------------|-----------|---------|---------------------|-----------------------|
| **0€** | 3 semaines | 11 | 8 req/5min | httpx[brotli], python-socketio, msgpack |

---

*Kontract.gg — Confidentiel — Mars 2026*
