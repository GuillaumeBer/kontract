# Module ui/

Dashboard Streamlit — interface utilisateur MVP de Kontract.gg.

## Fichier : `ui/dashboard.py`

### Lancement

```bash
streamlit run ui/dashboard.py
# Accessible sur http://localhost:8501
```

### Fonctionnalités

#### Sidebar — Filtres interactifs

| Filtre | Type | Défaut |
|--------|------|--------|
| ROI minimum | Slider 0–100% | 10% |
| Budget max 10x inputs | Input numérique | 200€ |
| Pool max (nb outcomes) | Slider 1–20 | 5 |
| Liquidité min (ventes/j) | Slider 0–50 | 0 |
| Source prix achat | Select skinport/steam | skinport |
| Source prix vente | Select skinport/steam | skinport |

Le bouton **"Scanner maintenant"** lance un scan à la demande.

#### Métriques globales

4 KPIs en haut de page :
- Nombre d'opportunités trouvées
- Meilleur ROI
- EV nette maximale
- Pool size moyen

#### Tableau des opportunités

Colonnes : Input skin, ROI (%), EV nette (€), Coût 10x (€), Pool size, Win prob (%), Liquidité (vol/j)

Coloration du ROI :
- 🟢 ROI ≥ 50% : vert foncé
- 🟢 ROI ≥ 20% : vert moyen
- 🟡 ROI ≥ 10% : vert clair

#### Vue détail

Sélecteur permettant d'inspecter une opportunité spécifique :
- Métriques complètes (left)
- Tableau des outputs possibles avec probabilités et prix (right)

### Architecture Streamlit

Le dashboard utilise `st.session_state` pour cacher les résultats du scan entre les reruns. Le scan ne se relance que lors du clic sur le bouton ou à la première visite.

```python
if scan_btn or "opportunities" not in st.session_state:
    opps = _run_scan(filters)
    st.session_state["opportunities"] = opps
```
