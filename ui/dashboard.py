"""
Module ui/dashboard.py
Dashboard Streamlit — Kontract.gg MVP

Lance avec :
  streamlit run ui/dashboard.py
"""

import json
from datetime import datetime

import pandas as pd
import streamlit as st

from data.database import get_session, init_db
from data.models import Opportunity, Price, Skin
from engine.scanner import UserFilters, scan_all_opportunities

st.set_page_config(
    page_title="Kontract.gg — CS2 Trade-Up Scanner",
    page_icon="🎯",
    layout="wide",
)

# Initialisation BDD au démarrage
init_db()


def _get_last_price_update() -> str:
    with get_session() as session:
        latest = session.query(Price).order_by(Price.updated_at.desc()).first()
        if latest and latest.updated_at:
            dt = latest.updated_at
            if hasattr(dt, 'strftime'):
                return dt.strftime("%H:%M:%S")
    return "Jamais"


def _run_scan(filters: UserFilters) -> list[dict]:
    return scan_all_opportunities(filters)


def _opportunities_to_df(opps: list[dict]) -> pd.DataFrame:
    if not opps:
        return pd.DataFrame()
    rows = []
    for opp in opps:
        rows.append({
            "Input skin": opp["input_name"],
            "ROI (%)": round(opp["roi"], 1),
            "EV nette (€)": round(opp["ev_nette"], 2),
            "Coût 10x (€)": round(opp["cout_ajuste"], 2),
            "Pool size": opp["pool_size"],
            "Win prob (%)": round(opp["win_prob"], 1),
            "Liquidité (vol/j)": round(opp["liquidity_score"], 1),
            "_combo_hash": opp["combo_hash"],
            "_outputs": opp.get("outputs", []),
        })
    return pd.DataFrame(rows)


# ─── Header ───────────────────────────────────────────────────────────────────
st.title("🎯 Kontract.gg — CS2 Trade-Up Scanner")
st.caption(f"Dernière mise à jour des prix : {_get_last_price_update()}")

# ─── Sidebar — Filtres ───────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Filtres")

    min_roi = st.slider("ROI minimum (%)", min_value=0, max_value=100, value=10, step=5)
    max_budget = st.number_input("Budget max 10x inputs (€)", min_value=10.0, max_value=10000.0,
                                  value=200.0, step=10.0)
    max_pool = st.slider("Pool max (nb outcomes)", min_value=1, max_value=20, value=5)
    min_liquidity = st.slider("Liquidité min (ventes/j)", min_value=0.0, max_value=50.0,
                               value=0.0, step=1.0)

    source_buy = st.selectbox("Source prix achat", ["skinport", "steam"], index=0)
    source_sell = st.selectbox("Source prix vente", ["skinport", "steam"], index=0)

    scan_btn = st.button("🔍 Scanner maintenant", type="primary", use_container_width=True)

    st.divider()
    st.caption("Sources : Skinport API · ByMykel CSGO-API · Steam Market")

# ─── Scan ─────────────────────────────────────────────────────────────────────
if scan_btn or "opportunities" not in st.session_state:
    filters = UserFilters(
        min_roi=float(min_roi),
        max_budget=max_budget,
        max_pool_size=max_pool,
        min_liquidity=min_liquidity,
        source_buy=source_buy,
        source_sell=source_sell,
    )
    with st.spinner("Scan en cours..."):
        opps = _run_scan(filters)
    st.session_state["opportunities"] = opps
    st.session_state["filters_used"] = filters
else:
    opps = st.session_state.get("opportunities", [])

# ─── Métriques globales ───────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("Opportunités trouvées", len(opps))

if opps:
    col2.metric("Meilleur ROI", f"{opps[0]['roi']:.1f}%")
    col3.metric("EV nette max", f"{opps[0]['ev_nette']:.2f}€")
    avg_pool = sum(o["pool_size"] for o in opps) / len(opps)
    col4.metric("Pool moyen", f"{avg_pool:.1f}")

st.divider()

# ─── Tableau des opportunités ─────────────────────────────────────────────────
if not opps:
    st.info("Aucune opportunité trouvée avec ces filtres. Essayez d'assouplir les critères.")
else:
    df = _opportunities_to_df(opps)
    display_cols = [c for c in df.columns if not c.startswith("_")]

    st.subheader(f"📊 {len(opps)} opportunités qualifiées")

    # Colorer le ROI
    def color_roi(val):
        if val >= 50:
            return "background-color: #1a472a; color: white"
        elif val >= 20:
            return "background-color: #2d6a4f; color: white"
        elif val >= 10:
            return "background-color: #74c69d"
        return ""

    styled = df[display_cols].style.applymap(color_roi, subset=["ROI (%)"])
    st.dataframe(styled, use_container_width=True, height=400)

    # ─── Vue détail ────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("🔎 Détail d'une opportunité")

    selected_name = st.selectbox(
        "Sélectionner un skin input",
        options=[o["input_name"] for o in opps],
        index=0,
    )

    selected = next((o for o in opps if o["input_name"] == selected_name), None)
    if selected:
        d1, d2 = st.columns(2)

        with d1:
            st.markdown(f"**Input** : {selected['input_name']}")
            st.markdown(f"**Coût 10x inputs** : {selected['cout_ajuste']:.2f}€")
            st.markdown(f"**EV nette** : {selected['ev_nette']:.2f}€")
            st.markdown(f"**ROI** : {selected['roi']:.1f}%")
            st.markdown(f"**Win probability** : {selected['win_prob']:.1f}%")
            st.markdown(f"**Pool size** : {selected['pool_size']} outcomes possibles")
            st.markdown(f"**Liquidité** : {selected['liquidity_score']:.1f} ventes/j")

        with d2:
            outputs = selected.get("outputs", [])
            if outputs:
                st.markdown("**Outputs possibles :**")
                out_df = pd.DataFrame([
                    {
                        "Skin": o["name"],
                        "Prob (%)": o["prob"],
                        "Prix vente (€)": o["sell_price"],
                        "Vol 24h": o["volume_24h"],
                    }
                    for o in outputs
                ])
                st.dataframe(out_df, use_container_width=True, hide_index=True)
