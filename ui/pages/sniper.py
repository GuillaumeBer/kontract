"""
Page UI — Sniper temps réel Skinport
Affiche les listings détectés en dessous du prix médian des inputs d'opportunités connues.
"""

import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from data.database import get_session
from data.models import SnipeAlert
from ui.utils import render_header

render_header("⚡ Sniper Temps Réel")

st.info(
    "Le sniper poll l'API Skinport toutes les 90s et détecte les listings "
    "en dessous du seuil de remise configuré dans `main.py` (env var `SNIPE_DISCOUNT`, défaut 12%)."
)

# ── Sidebar filtres ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Filtres")
    min_discount = st.slider("Remise minimum (%)", 0, 50, 10, 1)
    min_ks = st.number_input("KS minimum", 0.0, 10.0, 0.0, 0.1)
    time_window = st.selectbox("Fenêtre temporelle", ["1h", "6h", "24h", "7j", "Tout"], index=2)
    show_expired = st.checkbox("Afficher les listings expirés", False)
    st.divider()
    auto_refresh = st.checkbox("Auto-refresh (30s)", True)
    sort_by = st.selectbox("Trier par", ["detected_at", "discount_pct", "opp_roi_sniped", "opp_kontract_score"], 0)

# ── Chargement des snipes depuis BDD ────────────────────────────────────────
def _load_snipes(min_disc: float, min_ks_val: float, window: str, expired: bool) -> list[SnipeAlert]:
    cutoff_map = {
        "1h": timedelta(hours=1),
        "6h": timedelta(hours=6),
        "24h": timedelta(hours=24),
        "7j": timedelta(days=7),
        "Tout": None,
    }
    delta = cutoff_map.get(window)

    with get_session() as session:
        q = session.query(SnipeAlert)
        if not expired:
            q = q.filter(SnipeAlert.status == "active")
        if delta:
            cutoff = datetime.now(timezone.utc) - delta
            q = q.filter(SnipeAlert.detected_at >= cutoff)
        if min_disc > 0:
            q = q.filter(SnipeAlert.discount_pct >= min_disc)
        if min_ks_val > 0:
            q = q.filter(SnipeAlert.opp_kontract_score >= min_ks_val)
        rows = q.order_by(SnipeAlert.detected_at.desc()).limit(200).all()
        # Détacher les objets de la session avant de retourner
        return [
            {
                "id": r.id,
                "market_hash_name": r.market_hash_name,
                "listing_price": r.listing_price,
                "median_price": r.median_price,
                "discount_pct": r.discount_pct,
                "opp_roi_base": r.opp_roi_base,
                "opp_roi_sniped": r.opp_roi_sniped,
                "opp_kontract_score": r.opp_kontract_score,
                "item_url": r.item_url or "",
                "detected_at": r.detected_at,
                "status": r.status,
            }
            for r in rows
        ]


def _color_discount(val: float) -> str:
    if val >= 25:
        return "background-color: #1a4a1a; color: #00ff88"
    if val >= 15:
        return "background-color: #2a3a1a; color: #aaff44"
    if val >= 10:
        return "background-color: #3a3a1a; color: #ffee44"
    return ""


def _color_roi(val: float) -> str:
    if val >= 20:
        return "color: #00ff88"
    if val >= 10:
        return "color: #aaff44"
    if val >= 0:
        return "color: #ffee44"
    return "color: #ff4444"


# ── Métriques résumé ────────────────────────────────────────────────────────
snipes = _load_snipes(min_discount, min_ks, time_window, show_expired)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Snipes détectés", len(snipes))
if snipes:
    col2.metric("Remise max", f"{max(s['discount_pct'] for s in snipes):.1f}%")
    col3.metric("ROI boosté max", f"{max(s['opp_roi_sniped'] for s in snipes):.1f}%")
    best_ks = max(snipes, key=lambda s: s["opp_kontract_score"])
    col4.metric("KS max", f"{best_ks['opp_kontract_score']:.2f}")
else:
    col2.metric("Remise max", "—")
    col3.metric("ROI boosté max", "—")
    col4.metric("KS max", "—")

st.divider()

# ── Table principale ─────────────────────────────────────────────────────────
if not snipes:
    st.info("Aucun snipe détecté sur cette période. Le sniper WebSocket doit être actif dans `main.py`.")
else:
    sort_key = sort_by if sort_by != "detected_at" else "detected_at"
    snipes_sorted = sorted(snipes, key=lambda s: s[sort_key], reverse=(sort_key != "detected_at"))

    rows = []
    for s in snipes_sorted:
        detected = s["detected_at"]
        if detected and hasattr(detected, "strftime"):
            age = datetime.now(timezone.utc) - detected.replace(tzinfo=timezone.utc) if detected.tzinfo is None else datetime.now(timezone.utc) - detected
            age_str = f"{int(age.total_seconds() // 60)}min ago" if age.total_seconds() < 3600 else f"{int(age.total_seconds() // 3600)}h ago"
        else:
            age_str = "—"

        rows.append({
            "Skin": s["market_hash_name"],
            "Prix listé (€)": round(s["listing_price"], 2),
            "Médiane (€)": round(s["median_price"], 2),
            "Remise (%)": round(s["discount_pct"], 1),
            "ROI base (%)": round(s["opp_roi_base"] or 0, 1),
            "ROI boosté (%)": round(s["opp_roi_sniped"] or 0, 1),
            "KS": round(s["opp_kontract_score"] or 0, 2),
            "Détecté": age_str,
            "Statut": s["status"],
            "_url": s["item_url"],
            "_id": s["id"],
        })

    df = pd.DataFrame(rows)

    styled = (
        df[[c for c in df.columns if not c.startswith("_")]].style
        .applymap(_color_discount, subset=["Remise (%)"])
        .applymap(_color_roi, subset=["ROI boosté (%)"])
        .format({"Prix listé (€)": "{:.2f}", "Médiane (€)": "{:.2f}",
                 "Remise (%)": "{:.1f}", "ROI base (%)": "{:.1f}",
                 "ROI boosté (%)": "{:.1f}", "KS": "{:.2f}"})
    )

    event = st.dataframe(
        styled,
        use_container_width=True,
        height=420,
        on_select="rerun",
        selection_mode="single-row",
        key="snipes_df",
    )

    # ── Détail du snipe sélectionné ──────────────────────────────────────────
    if event.selection.rows:
        sel = rows[event.selection.rows[0]]
        st.divider()
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader(f"🎯 {sel['Skin']}")
            st.write(f"**Prix listé** : `{sel['Prix listé (€)']:.2f}€` vs médiane `{sel['Médiane (€)']:.2f}€`")
            st.write(f"**Remise** : `{sel['Remise (%)']:.1f}%`")
            st.write(f"**ROI trade-up** : `{sel['ROI base (%)']:.1f}%` → `{sel['ROI boosté (%)']:.1f}%` avec ce prix")
            st.write(f"**Kontract Score** : `{sel['KS']:.2f}`")
            st.write(f"**Détecté** : {sel['Détecté']}")
        with c2:
            url = sel["_url"]
            if url:
                st.link_button("🛒 Acheter sur Skinport", url, type="primary", use_container_width=True)
            else:
                st.warning("Lien Skinport non disponible")

            # Bouton marquer comme acheté
            if st.button("✅ Marquer comme acheté", key=f"bought_{sel['_id']}", use_container_width=True):
                with get_session() as session:
                    row = session.query(SnipeAlert).filter_by(id=sel["_id"]).first()
                    if row:
                        row.status = "bought"
                        session.commit()
                st.success("Statut mis à jour !")
                st.rerun()

# ── Auto-refresh ─────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(30)
    st.rerun()
