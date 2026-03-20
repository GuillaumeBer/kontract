import streamlit as st
import pandas as pd
from data.database import get_session
from data.models import TradeupBasket, BasketItem, Skin
from ui.utils import get_last_price_update, get_next_update_timer, render_header

render_header("💼 Portefeuille — Paniers Actifs")

# Avertissement
st.info("Visualisez ici l'avancement de vos trade-ups en cours et la répartition du capital.")

with get_session() as session:
    baskets = session.query(TradeupBasket).filter_by(status="active").all()
    
    if not baskets:
        st.info("Aucun panier actif. Utilisez le Scanner pour en créer un.")
    else:
        # Global metrics
        total_invested = 0
        total_items = 0
        for b in baskets:
            for item in b.items:
                total_invested += item.buy_price
                total_items += 1
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Paniers Actifs", len(baskets))
        c2.metric("Total Investi", f"{total_invested:.2f}€")
        c3.metric("Slots Utilisés", f"{len(baskets)}/5")

        st.divider()

        # Basket Cards
        for basket in baskets:
            with st.expander(f"📦 {basket.input_skin_id} ({len(basket.items)}/10) - ROI Cible: {basket.target_roi or 0}%"):
                cols = st.columns([2, 1, 1])
                
                # Progress bar
                progress = len(basket.items) / 10
                cols[0].progress(progress, text=f"Remplissage : {len(basket.items)}/10 items")
                
                # Items list
                item_rows = []
                for item in basket.items:
                    # In real we'd fetch skin name
                    item_rows.append({
                        "Skin ID": item.skin_id,
                        "Prix": f"{item.buy_price:.2f}€",
                        "Float": item.float_value or 0.0,
                        "Date": item.date_bought.strftime("%d/%m %H:%M")
                    })
                
                if item_rows:
                    item_df = pd.DataFrame(item_rows)
                    st.dataframe(item_df, use_container_width=True, hide_index=True)
                else:
                    st.write("Panier vide.")
                
                col_a, col_b = st.columns(2)
                if col_a.button("Exécuter Trade-up", key=f"exec_{basket.id}"):
                    st.success(f"Exécution du trade-up {basket.id} enregistrée !")
                if col_b.button("Abandonner Panier", key=f"ab_{basket.id}"):
                    st.warning(f"Panier {basket.id} abandonné.")
