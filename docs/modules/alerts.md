# Module alerts/

Matching des opportunités avec les profils utilisateurs et envoi d'alertes Telegram.

## Fichiers

### `alerts/notifier.py`

#### `match_opportunities_to_users(opportunities) -> list[tuple[str, str]]`

Pour chaque opportunité, cherche les utilisateurs dont les filtres correspondent et retourne les couples `(chat_id, message_formaté)`.

**Critères de matching** :
- `roi >= user.min_roi`
- `cout_ajuste <= user.max_budget`
- `pool_size <= user.max_pool_size`
- `liquidity_score >= user.min_liquidity` (si > 0)
- `user.active == True`

**Format du message Telegram** :
```
🎯 *Trade-up Profitable Détecté !*

*Input* : Galil AR | Hunting Blind
*ROI* : 254.4%
*EV nette* : 68.11€
*Coût 10x* : 26.77€
*Pool size* : 5 outcomes
*Win prob* : 40.0%

*Outputs possibles* :
  • SSG 08 | Tropical Storm: 20.0% → 390.95€
  • Glock-18 | Groundwater: 20.0% → 30.50€
  ...
```

---

### `alerts/telegram_bot.py`

Bot Telegram avec commandes utilisateur.

#### Commandes

| Commande | Description |
|----------|-------------|
| `/start` | Inscription + affichage du profil par défaut |
| `/profil` | Afficher les paramètres actuels |
| `/config roi=15 pool=3 budget=200 liquidity=5` | Modifier les filtres |
| `/pause` | Désactiver les alertes |
| `/resume` | Réactiver les alertes |
| `/scan` | Lancer un scan immédiat et voir le top 5 |

#### Démarrage

```bash
export TELEGRAM_BOT_TOKEN=your_bot_token
python -m alerts.telegram_bot
```

#### Fonctions clés

**`send_notifications(notifications, token) -> None`**

Envoie une liste de `(chat_id, message)` via l'API Telegram. Gère les erreurs par utilisateur sans bloquer les autres.

**`build_application(token) -> Application`**

Construit l'application python-telegram-bot avec tous les handlers enregistrés. Utilisée dans `main.py` pour lancer le bot en parallèle du scheduler.

#### Profil par défaut

```python
UserAlert(
    min_roi=10.0,         # ROI min 10%
    max_budget=100.0,     # budget max 100€
    max_pool_size=5,      # pool max 5 outcomes
    min_liquidity=3.0,    # 3 ventes/jour minimum
    source_buy="skinport",
    source_sell="skinport",
    active=True,
)
```

## Utilisation dans le cycle principal

```python
from engine.scanner import scan_all_opportunities, UserFilters
from alerts.notifier import match_opportunities_to_users
from alerts.telegram_bot import send_notifications
import asyncio

opps = scan_all_opportunities(UserFilters())
notifications = match_opportunities_to_users(opps)
asyncio.run(send_notifications(notifications, token=TELEGRAM_BOT_TOKEN))
```
