import streamlit as st
import pandas as pd
from data.database import get_session
from data.models import Opportunity
from engine.scanner import UserFilters, scan_all_opportunities
from ui.utils import get_last_price_update, get_next_update_timer, render_header, color_ks, color_roi, color_win, color_rel
from engine.filters import rank_input_listings
from fetcher.listings import fetch_listings_mock
from basket.panier_state import get_or_create_basket, add_item_to_basket

# Page Configuration (st.set_page_config is already in dashboard.py)

def _run_scan(filters: UserFilters) -> list[dict]:
    return scan_all_opportunities(filters)

def _opportunities_to_df(opps: list[dict]) -> pd.DataFrame:
    if not opps:
        return pd.DataFrame()
    rows = []
    for opp in opps:
        liq_status = opp.get("input_liquidity_status", "liquid")
        liq_emoji = {"liquid": "🟢", "partial": "🟡", "scarce": "🔴"}.get(liq_status, "⚪")
        max_reps = opp.get("max_repeats", 0) or 0
        inputs_label = f"{liq_emoji} x{max_reps}"
        vel = "⚡ " if opp.get("velocity_alert") else ""
        rows.append({
            "Input skin": f"{vel}{opp['input_name']}",
            "Kontract Score": round(opp.get("kontract_score", 0.0), 2),
            "ROI (%)": round(opp["roi"], 1),
            "Win prob (%)": round(opp["win_prob"], 1),
            "Floor (%)": round((opp.get("floor_ratio", 0.0) or 0.0) * 100, 1),
            "Fiabilité": opp.get("price_reliability", "low").upper(),
            "EV nette (€)": round(opp["ev_nette"], 2),
            "Coût (€)": round(opp["cout_ajuste"], 2),
            "Pool": opp["pool_size"],
            "Inputs": inputs_label,
            "Strat": opp.get("strategy_used", "pure"),
            "Liquidité": round(opp["liquidity_score"], 1),
            "_combo_hash": opp["combo_hash"],
            "_outputs": opp.get("outputs", []),
        })
    return pd.DataFrame(rows)

render_header("🔍 Scanner d'Opportunités EV")

# Avertissement
st.warning("⚠️ Risque systémique Valve : Les opportunités peuvent expirer sans préavis.")

# Sidebar Filters
with st.sidebar:
    st.header("⚙️ Filtres")
    min_roi = st.slider("ROI minimum (%)", 0, 100, 0, 5)  # Aligné sur main.py (0%)
    max_budget = st.number_input("Budget max (€)", 10.0, 10000.0, 400.0, 10.0)  # Aligné sur main.py (400€)
    max_pool = st.slider("Pool max", 1, 20, 15)  # Aligné sur main.py (15)
    min_vol_sell = st.slider("Volume min (30j)", 0, 100, 10)  # Aligné sur main.py (10)
    min_liq = st.slider("Liquidité min (score)", 0.0, 10.0, 1.0, 0.5)  # Spec §4.5
    exclude_down = st.checkbox("Exclure tendances baissières", False)
    exclude_volatility = st.checkbox("Exclure haute volatilité", False)
    min_ks = st.number_input("KS min", 0.0, 100.0, 0.0, 0.5)
    source_buy = st.selectbox("Source achat", ["skinport", "steam"], 0)
    source_sell = st.selectbox("Source vente", ["skinport", "steam"], 0)
    st.divider()
    sort_by = st.selectbox("Trier par", ["Kontract Score", "ROI (%)", "EV nette (€)", "Win prob (%)"], 0)
    scan_btn = st.button("🔍 Lancer le Scan", type="primary", use_container_width=True)

# logic
# Generate active filters signature to detect changes
current_filters_sig = f"{min_roi}-{max_budget}-{max_pool}-{min_vol_sell}-{exclude_down}-{exclude_volatility}-{min_ks}-{source_buy}-{source_sell}"

if "filters_sig" not in st.session_state or st.session_state["filters_sig"] != current_filters_sig or scan_btn:
    filters = UserFilters(
        min_roi=float(min_roi), max_budget=max_budget, max_pool_size=max_pool,
        min_volume_sell_price=min_vol_sell, min_liquidity=min_liq,
        exclude_trending_down=exclude_down,
        exclude_high_volatility=exclude_volatility, min_kontract_score=min_ks,
        source_buy=source_buy, source_sell=source_sell
    )
    with st.spinner("Recherche des meilleures opportunités..."):
        opps = _run_scan(filters)
    st.session_state["opportunities"] = opps
    st.session_state["filters_sig"] = current_filters_sig
else:
    opps = st.session_state.get("opportunities", [])

if not opps:
    st.info("Aucune opportunité trouvée.")
else:
    df = _opportunities_to_df(opps)
    sort_col = sort_by if sort_by in df.columns else "Kontract Score"
    df = df.sort_values(sort_col, ascending=False)

    styled = (
        df[[c for c in df.columns if not c.startswith("_")]].style
        .applymap(color_ks, subset=["Kontract Score"])
        .applymap(color_roi, subset=["ROI (%)"])
        .applymap(color_win, subset=["Win prob (%)"])
        .applymap(color_rel, subset=["Fiabilité"])
    )

    event = st.dataframe(styled, use_container_width=True, height=400, on_select="rerun", selection_mode="single-row", key="opps_df")

    # Detail View
    if event.selection.rows:
        sel_idx = event.selection.rows[0]
        selected = next((o for o in opps if o["combo_hash"] == df.iloc[sel_idx]["_combo_hash"]), None)
        
        if selected:
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.subheader(f"Détail : {selected['input_name']}")
                st.write(f"**Kontract Score**: {selected.get('kontract_score', 0):.2f}")
                st.write(f"**ROI**: {selected['roi']:.1f}% | **Prob**: {selected['win_prob']:.1f}%")
                st.write(f"**EV**: {selected['ev_nette']:.2f}€ | **Coût**: {selected['cout_ajuste']:.2f}€")
                st.write(f"**Fiabilité**: {selected.get('price_reliability', 'low').upper()}")
                
                if selected.get("strategy_used") == "fillers":
                    st.write("---")
                    st.write("**🛡️ Stratégie MIXTE (Fillers) :**")
                    st.write(f"Vouz devez acheter **7x** {selected['input_name']}")
                    st.write("**PLUS 3 items parmi les fillers suivants :**")
                    for f_name in selected.get("filler_skins", []):
                        st.write(f"- {f_name}")
                    st.info("💡 Les fillers sont des items 'bon marché' d'autres collections utilisés pour réduire le coût moyen sans polluer le résultat final.")
                
            with col2:
                st.write("**Outputs :**")
                out_df = pd.DataFrame(selected.get("outputs", []))
                st.dataframe(out_df[["name", "prob", "sell_price"]], hide_index=True)
                
                # Chart visualization: Historical Trend (§4.3)
                if not out_df.empty:
                    # Reformater pour un graphique linéaire multicoubes
                    trend_data = []
                    time_points = [
                        ("90j", "median_90d"),
                        ("30j", "median_30d"),
                        ("7j", "median_7d"),
                        ("24h", "median_24h"),
                        ("Maintenant", "sell_price")
                    ]
                    
                    for _, row in out_df.iterrows():
                        skin_name = row["name"]
                        for label, col in time_points:
                            val = row.get(col)
                            if val and val > 0:
                                trend_data.append({
                                    "Time": label,
                                    "Skin": skin_name,
                                    "Prix (€)": float(val)
                                })
                    
                    if trend_data:
                        st.write("**Tendance des prix (historique) :**")
                        trend_df = pd.DataFrame(trend_data)
                        # S'assurer que l'ordre temporel est respecté
                        trend_df["Time"] = pd.Categorical(trend_df["Time"], categories=[p[0] for p in time_points], ordered=True)
                        st.line_chart(trend_df, x="Time", y="Prix (€)", color="Skin")
                    else:
                        st.info("Données historiques insuffisantes pour le graphique.")
