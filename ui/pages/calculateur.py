import streamlit as st
import pandas as pd
from data.database import get_session
from data.models import Skin, TradeupPool, Price, Collection
from engine.ev_calculator import InputSkin, OutputSkin, calculate_ev
from ui.utils import get_last_price_update

# st.set_page_config removed as it's handled by dashboard.py

st.title("🧮 Calculateur EV — Trade-Up Manuel")
st.caption(f"Dernière mise à jour : {get_last_price_update()}")

# ─── Chargement des données ─────────────────────────────────────────
with get_session() as session:
    collections = session.query(Collection).filter_by(active=True).order_by(Collection.name).all()
    coll_map = {c.name: c.id for c in collections}
    all_skins = session.query(Skin).filter(Skin.market_hash_name.isnot(None)).all()
    prices_rows = session.query(Price).filter_by(platform="skinport").all()
    prices_idx = {p.skin_id: p for p in prices_rows}

# ─── Sélection ─────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("⚙️ Paramètres")
    
    use_fillers = st.checkbox("Utiliser des fillers (7+3)", value=False)
    
    selected_coll_name = st.selectbox("Collection Cible", list(coll_map.keys()), index=0)
    selected_coll_id = coll_map.get(selected_coll_name)

    # Filter skins
    coll_skins = [s for s in all_skins if s.collection_id == selected_coll_id and s.id in prices_idx]
    coll_skins.sort(key=lambda s: s.name)
    
    if not coll_skins:
        st.warning("Aucun skin dispo.")
        st.stop()

    skin_names = [s.name for s in coll_skins]
    selected_skin_name = st.selectbox("Skin Target", skin_names, index=0)
    selected_skin = next(s for s in coll_skins if s.name == selected_skin_name)
    
    # Filler selection
    filler_skin = None
    if use_fillers:
        filler_coll_name = st.selectbox("Collection Filler", list(coll_map.keys()), index=1)
        f_coll_id = coll_map.get(filler_coll_name)
        f_skins = [s for s in all_skins if s.collection_id == f_coll_id and s.rarity_id == selected_skin.rarity_id and s.id in prices_idx]
        if f_skins:
            f_names = [s.name for s in f_skins]
            f_selected_name = st.selectbox("Skin Filler", f_names, index=0)
            filler_skin = next(s for s in f_skins if s.name == f_selected_name)
        else:
            st.error("Aucun filler de même tier trouvé dans cette collection.")

    calc_btn = st.button("📐 Calculer EV", type="primary", use_container_width=True)

# ─── Calcul ─────────────────────────────────────────────────────────
if calc_btn:
    with col_right:
        with get_session() as session:
            # Target outputs
            target_out_ids = [tp.output_skin_id for tp in session.query(TradeupPool).filter_by(input_skin_id=selected_skin.id).all()]
            
            # Build input list
            buy_price = prices_idx[selected_skin.id].buy_price
            n_target = 7 if use_fillers else 10
            inputs = [InputSkin(selected_skin.id, selected_skin.name, selected_coll_id, selected_skin.rarity_id, buy_price) for _ in range(n_target)]
            
            outputs_by_coll = {selected_coll_id: []}
            for out_id in target_out_ids:
                p = prices_idx.get(out_id)
                s = next((sk for sk in all_skins if sk.id == out_id), None)
                if s:
                    outputs_by_coll[selected_coll_id].append(OutputSkin(
                        skin_id=out_id, name=s.name,
                        sell_price=p.sell_price if p else 0,
                        volume_24h=p.volume_24h or 0.0 if p else 0.0,
                        volume_7d=p.volume_7d or 0.0 if p else 0.0,
                        volume_30d=p.volume_30d or 0.0 if p else 0.0,
                        quantity=p.quantity or 0 if p else 0,
                        median_24h=p.median_24h if p else None,
                        median_7d=p.median_7d if p else None,
                        median_30d=p.median_30d if p else None,
                        median_90d=p.median_90d if p else None,
                        avg_24h=p.avg_24h if p else None,
                        avg_7d=p.avg_7d if p else None,
                        avg_30d=p.avg_30d if p else None,
                        avg_90d=p.avg_90d if p else None,
                    ))

            if use_fillers and filler_skin:
                f_price = prices_idx[filler_skin.id].buy_price
                inputs += [InputSkin(filler_skin.id, filler_skin.name, filler_skin.collection_id, filler_skin.rarity_id, f_price) for _ in range(3)]

                f_out_ids = [tp.output_skin_id for tp in session.query(TradeupPool).filter_by(input_skin_id=filler_skin.id).all()]
                outputs_by_coll[filler_skin.collection_id] = []
                for out_id in f_out_ids:
                    p = prices_idx.get(out_id)
                    s = next((sk for sk in all_skins if sk.id == out_id), None)
                    if s:
                        outputs_by_coll[filler_skin.collection_id].append(OutputSkin(
                            skin_id=out_id, name=s.name,
                            sell_price=p.sell_price if p else 0,
                            volume_24h=p.volume_24h or 0.0 if p else 0.0,
                            volume_7d=p.volume_7d or 0.0 if p else 0.0,
                            volume_30d=p.volume_30d or 0.0 if p else 0.0,
                            quantity=p.quantity or 0 if p else 0,
                            median_24h=p.median_24h if p else None,
                            median_7d=p.median_7d if p else None,
                            median_30d=p.median_30d if p else None,
                            median_90d=p.median_90d if p else None,
                            avg_24h=p.avg_24h if p else None,
                            avg_7d=p.avg_7d if p else None,
                            avg_30d=p.avg_30d if p else None,
                            avg_90d=p.avg_90d if p else None,
                        ))

            try:
                res = calculate_ev(inputs, outputs_by_coll)
                # Results display
                st.metric("ROI", f"{res.roi:.1f}%")
                st.metric("EV nette", f"{res.ev_nette:.2f}€")
                out_df = pd.DataFrame(res.outputs)
                st.dataframe(out_df[["name", "prob", "sell_price"]], hide_index=True)
                
                # Chart visualization: Historical Trend (§4.3)
                if not out_df.empty:
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
                        trend_df["Time"] = pd.Categorical(trend_df["Time"], categories=[p[0] for p in time_points], ordered=True)
                        st.line_chart(trend_df, x="Time", y="Prix (€)", color="Skin")
            except Exception as e:
                st.error(f"Erreur : {e}")
