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
               volume_24h, volume_7d, updated_at
user_alerts  : user_id, min_roi, max_budget, max_pool_size,
               min_liquidity, source_buy, source_sell, active
opportunities: id, combo_hash, inputs_json, ev_nette, roi,
               pool_size, liquidity_score, created_at
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

#### Formule EV complète — post-mise à jour octobre 2025

```python
# ÉTAPE 1 : Probabilités selon la composition des 10 inputs
# Exemple : 7 inputs collection A + 3 inputs collection B
prob(output_X in A) = (7/10) × (1 / nb_outputs_tier_sup_A)
prob(output_Y in B) = (3/10) × (1 / nb_outcomes_tier_sup_B)

# ÉTAPE 2 : Détermination du prix de vente espéré — logique de fallback
# Le prix de vente d'un output n'est pas le prix spot, mais la médiane historique.
def get_sell_price(out):
    if out.volume_7d >= min_vol_7d: return out.median_7d, "high"
    if out.volume_30d >= 15:        return out.median_30d, "medium"
    if out.sell_price > 0:          return out.sell_price, "low"
    return None, "insufficient"

# ÉTAPE 3 : EV brute + redistribution
# Si un output est "insufficient", son poids est redistribué proportionnellement aux autres.
EV_brute = Σ (prob_redistribuée_i × prix_fallback_i)

# ÉTAPE 4 : Coût ajusté selon plateforme achat
# Skinport = 5% acheteur | Steam = 15%
cout_ajuste = Σ prix_input_j × (1 + frais_achat)

# ÉTAPE 5 : EV nette après frais de vente
# Skinport = 3% vendeur | Steam = 15%
EV_nette = EV_brute × (1 - frais_vente) - cout_ajuste

# ÉTAPE 6 : ROI et métriques scoring
ROI        = (EV_nette / cout_ajuste) × 100
reliability = min(reliability_of_all_outputs)  # Score global de l'opportunité
win_prob   = Σ prob_i où prix_output_i > cout_ajuste
```

#### Critères de filtrage — configurables par utilisateur

| Critère | Défaut | Plage | Source données | Impact |
|---------|--------|-------|---------------|--------|
| ROI minimum | 10% | 5–50% | Moteur EV | Filtre principal de rentabilité |
| Pool max (nb outcomes) | 5 | 1–20 | ByMykel collections | Concentration — différenciateur clé |
| Liquidité min (ventes/7j) | 0 | 0–50 | Skinport /v1/sales/history | Liquidité à la revente |
| Volume min prix vente (7j) | 7 | 3–30 | Skinport /v1/sales/history | Fiabilité du prix utilisé pour l'EV |
| Budget max inputs | 200 € | 10–10 000 € | Skinport /v1/items | Capital max par trade-up |
| Source prix achat | Skinport | Skinport / Steam | Skinport /v1/items | Impact sur le coût ajusté |
| Source prix vente | Skinport | Skinport / Steam | Skinport /v1/items | Impact sur l'EV nette |

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
