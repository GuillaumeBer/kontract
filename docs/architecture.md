# Architecture — Kontract.gg

## Vue d'ensemble

```
┌─────────────────────────────────────────────────────────┐
│                      main.py                            │
│              APScheduler (async)                        │
│  ┌──────────────────┐    ┌───────────────────────────┐  │
│  │  toutes les 5min │    │      1x / semaine         │  │
│  │  job_fetch_scan  │    │   job_update_bymykel      │  │
│  └────────┬─────────┘    └───────────┬───────────────┘  │
└───────────┼──────────────────────────┼──────────────────┘
            │                          │
            ▼                          ▼
┌───────────────────┐      ┌───────────────────────────┐
│   fetcher/        │      │   data/bymykel.py          │
│  skinport.py      │      │   ByMykel CSGO-API         │
│  steam.py         │      │   collections.json         │
└────────┬──────────┘      │   skins.json               │
         │                 └───────────┬───────────────┘
         ▼                             ▼
┌─────────────────────────────────────────────────────────┐
│                   SQLite (kontract.db)                  │
│  collections │ skins │ tradeup_pool │ prices │          │
│  user_alerts │ opportunities                           │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │    engine/           │
              │  ev_calculator.py    │
              │  scanner.py          │
              └──────────┬───────────┘
                         │
              ┌──────────┴───────────┐
              ▼                      ▼
  ┌─────────────────┐    ┌───────────────────────┐
  │  alerts/        │    │  ui/dashboard.py      │
  │  notifier.py    │    │  Streamlit             │
  │  telegram_bot   │    │  http://localhost:8501 │
  └─────────────────┘    └───────────────────────┘
```

## Flux de données

1. **Hebdomadaire** : `bymykel.py` télécharge `collections.json` + `skins.json` → peuple `collections`, `skins`, `tradeup_pool`

2. **Toutes les 5 min** :
   - `skinport.py` fetch `/v1/items` + `/v1/sales/history` → met à jour `prices` (si variation > 0.5%)
   - `scanner.py` évalue ~1100 combos trade-up → filtre par ROI/budget/pool/liquidité
   - `notifier.py` matche les opportunités avec les `user_alerts` actives
   - `telegram_bot.py` envoie les alertes

3. **À la demande** (dashboard) : `scan_all_opportunities(filters)` avec les filtres de l'utilisateur

## Sources de données

| Source | Endpoint | Fréquence | Auth |
|--------|---------|-----------|------|
| ByMykel CSGO-API | `raw.githubusercontent.com/ByMykel/CSGO-API/` | 1x/semaine | Aucune |
| Skinport `/v1/items` | `api.skinport.com/v1/items` | 5 min | Aucune (Accept-Encoding: br obligatoire) |
| Skinport `/v1/sales/history` | `api.skinport.com/v1/sales/history` | 5 min | Aucune |
| Steam Market | `steamcommunity.com/market/priceoverview/` | 10 min | Aucune |

**Coût total données : 0€**

## Performances MVP

| Opération | Durée observée |
|-----------|---------------|
| Chargement ByMykel (2622 skins) | ~3s |
| Fetch Skinport items | ~2s |
| Fetch Skinport history | ~2s |
| Scan complet (1099 combos) | < 1s |

## Environnement

Variables d'environnement (voir `.env.example`) :
- `TELEGRAM_BOT_TOKEN` — token BotFather
- `DATABASE_URL` — `sqlite:///./kontract.db` par défaut
- `REDIS_URL` — optionnel, Redis désactivé si non disponible

## Déploiement Railway

```bash
# Procfile
web: streamlit run ui/dashboard.py --server.port $PORT
worker: python main.py
```

Coût estimé : ~7$/mois (Railway Starter).
