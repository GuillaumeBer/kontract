"""
Page Calculateur — Kontract.gg
Permet de calculer manuellement l'EV d'un trade-up en sélectionnant
collection, input skin, et paramètres.
"""

import streamlit as st
import pandas as pd

from data.database import get_session, init_db
from data.models import Skin, TradeupPool, Price, Collection
from engine.ev_calculator import InputSkin, OutputSkin, calculate_ev

init_db()

st.set_page_config(page_title="Kontract.gg — Calculateur", page_icon="🔢", layout="wide")
st.title("🔢 Calculateur EV — Trade-Up Manuel")
st.caption("Sélectionnez une collection et un skin input pour calculer l'EV du trade-up.")

# ─── Chargement des données ─────────────────────────────────────────
with get_session() as session:
    collections = session.query(Collection).filter_by(active=True).order_by(Collection.name).all()
    coll_map = {c.name: c.id for c in collections}

    all_skins = session.query(Skin).filter(Skin.market_hash_name.isnot(None)).all()
    skins_by_coll: dict[str, list] = {}
    for s in all_skins:
        skins_by_coll.setdefault(s.collection_id, []).append(s)

    prices_rows = session.query(Price).filter_by(platform="skinport").all()
    prices_idx = {p.skin_id: p for p in prices_rows}

# ─── Sélection ─────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("⚙️ Paramètres")

    selected_coll_name = st.selectbox(
        "Collection",
        list(coll_map.keys()),
        index=0,
        help="Sélectionnez la collection cible du trade-up.",
    )
    selected_coll_id = coll_map.get(selected_coll_name)

    # Filter skins for this collection that have prices
    coll_skins = [
        s for s in skins_by_coll.get(selected_coll_id, [])
        if s.id in prices_idx and prices_idx[s.id].buy_price
    ]
    coll_skins.sort(key=lambda s: s.name)

    if not coll_skins:
        st.warning("Aucun skin avec prix disponible dans cette collection.")
        st.stop()

    # Group by rarity for selection
    RARITY_ORDER = [
        "rarity_common_weapon", "rarity_uncommon_weapon", "rarity_rare_weapon",
        "rarity_mythical_weapon", "rarity_legendary_weapon", "rarity_ancient_weapon",
    ]
    RARITY_LABELS = {
        "rarity_common_weapon": "Consumer Grade (gris)",
        "rarity_uncommon_weapon": "Industrial Grade (bleu clair)",
        "rarity_rare_weapon": "Mil-Spec (bleu)",
        "rarity_mythical_weapon": "Restricted (violet)",
        "rarity_legendary_weapon": "Classified (rose)",
        "rarity_ancient_weapon": "Covert (rouge)",
    }

    available_rarities = sorted(
        set(s.rarity_id for s in coll_skins),
        key=lambda r: RARITY_ORDER.index(r) if r in RARITY_ORDER else 99,
    )
    rarity_options = [RARITY_LABELS.get(r, r) for r in available_rarities]
    selected_rarity_label = st.selectbox("Tier du skin input", rarity_options, index=0)
    selected_rarity = available_rarities[rarity_options.index(selected_rarity_label)]

    tier_skins = [s for s in coll_skins if s.rarity_id == selected_rarity]
    if not tier_skins:
        st.warning("Aucun skin de ce tier dans cette collection.")
        st.stop()

    skin_names = [s.name for s in tier_skins]
    selected_skin_name = st.selectbox("Skin input", skin_names, index=0)
    selected_skin = next(s for s in tier_skins if s.name == selected_skin_name)

    n_inputs = 5 if selected_rarity == "rarity_ancient_weapon" else 10
    st.info(f"Nombre d'inputs : **{n_inputs}** ({'Covert → 5' if n_inputs == 5 else 'Standard → 10'})")

    source_buy = st.selectbox("Source achat", ["skinport", "steam"], index=0)
    source_sell = st.selectbox("Source vente", ["skinport", "steam"], index=0)

    calc_btn = st.button("📐 Calculer EV", type="primary", use_container_width=True)

# ─── Calcul ─────────────────────────────────────────────────────────
with col_right:
    if not calc_btn:
        st.info("Sélectionnez vos paramètres et cliquez sur **Calculer EV**.")
        st.stop()

    # Get outputs from tradeup_pool
    with get_session() as session:
        output_ids = [
            tp.output_skin_id
            for tp in session.query(TradeupPool).filter_by(
                input_skin_id=selected_skin.id,
                collection_id=selected_coll_id,
            ).all()
        ]

    if not output_ids:
        st.error("Aucun output trouvé dans le pool trade-up pour ce skin/collection.")
        st.stop()

    # Build input and output objects
    price_data = prices_idx.get(selected_skin.id)
    buy_price = price_data.buy_price if price_data else 0.0

    inputs_list = [
        InputSkin(
            skin_id=selected_skin.id,
            name=selected_skin.name,
            collection_id=selected_coll_id,
            rarity_id=selected_rarity,
            buy_price=buy_price,
            source_buy=source_buy,
        )
        for _ in range(n_inputs)
    ]

    outputs_list = []
    for out_id in output_ids:
        p = prices_idx.get(out_id)
        out_skin = next((s for s in all_skins if s.id == out_id), None)
        if not out_skin:
            continue
        outputs_list.append(OutputSkin(
            skin_id=out_id,
            name=out_skin.name,
            sell_price=p.sell_price if p else 0.0,
            volume_24h=p.volume_24h or 0.0 if p else 0.0,
            volume_7d=p.volume_7d or 0.0 if p else 0.0,
            volume_30d=p.volume_30d or 0.0 if p else 0.0,
            median_24h=p.median_24h if p else None,
            median_7d=p.median_7d if p else None,
            median_30d=p.median_30d if p else None,
            median_90d=p.median_90d if p else None,
            avg_24h=p.avg_24h if p else None,
            avg_7d=p.avg_7d if p else None,
            avg_30d=p.avg_30d if p else None,
            avg_90d=p.avg_90d if p else None,
            source_sell=source_sell,
        ))

    if not outputs_list:
        st.error("Aucun output avec données de prix disponibles.")
        st.stop()

    try:
        result = calculate_ev(
            inputs_list,
            {selected_coll_id: outputs_list},
            source_buy=source_buy,
            source_sell=source_sell,
        )
    except ValueError as e:
        st.error(f"Erreur de calcul : {e}")
        st.stop()

    # ─── Affichage des résultats ────────────────────────────────────
    st.subheader("📊 Résultats")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("EV nette", f"{result.ev_nette:.2f}€")
    m2.metric("ROI", f"{result.roi:.1f}%")
    m3.metric("Kontract Score", f"{result.kontract_score:.2f}")
    m4.metric("Win prob", f"{result.win_prob:.1f}%")

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Coût inputs", f"{result.cout_ajuste:.2f}€")
    m6.metric("Floor ratio", f"{result.floor_ratio:.1%}")
    m7.metric("CV pondéré", f"{result.cv_pond:.3f}")
    m8.metric("Fiabilité", result.price_reliability.upper())

    st.divider()
    st.subheader("🎯 Outcomes possibles")

    out_df = pd.DataFrame([
        {
            "Skin": o["name"],
            "Prob (%)": o["prob"],
            "Prix vente (€)": round(o["sell_price"], 2),
            "Vol 7j": o.get("volume_7d", 0),
            "État": o.get("reliability", "low").upper(),
        }
        for o in result.outputs
    ])
    st.dataframe(out_df, use_container_width=True, hide_index=True)

    # Price evolution chart
    st.subheader("📈 Évolution des prix des outputs")
    chart_data = {}
    for o in result.outputs:
        p90 = o.get("median_90d") or o["sell_price"]
        p30 = o.get("median_30d") or o["sell_price"]
        p7  = o.get("median_7d")  or o["sell_price"]
        p1  = o.get("median_24h") or o["sell_price"]
        p0  = o["sell_price"]
        chart_data[o["name"]] = [p90, p30, p7, p1, p0]

    if chart_data:
        time_labels = ["90 jours", "30 jours", "7 jours", "24 heures", "Maintenant"]
        chart_df = pd.DataFrame(chart_data, index=time_labels)
        chart_df.index = pd.Categorical(chart_df.index, categories=time_labels, ordered=True)
        st.line_chart(chart_df, use_container_width=True)
