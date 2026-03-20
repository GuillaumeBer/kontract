import streamlit as st
import pandas as pd
from data.database import get_session
from data.models import TradeupBasket, Opportunity, Skin, Price
from engine.recommender import ActionRecommender, ActionType, ActionPriority
from ui.utils import get_last_price_update, get_next_update_timer, render_header

render_header("📋 Plan d'Action")

# Avertissement
st.warning("⚠️ Suivez les actions par ordre de priorité pour maximiser la vélocité du capital.")

with get_session() as session:
    baskets = session.query(TradeupBasket).filter_by(status="active").all()
    # Fetch top opportunities with names from Skin table
    opps_raw = session.query(Opportunity).order_by(Opportunity.kontract_score.desc()).limit(15).all()
    opps = []
    for o in opps_raw:
        # Extract ID from combo_hash
        input_id = o.combo_hash.split(":")[0]
        skin_obj = session.get(Skin, input_id)
        
        # Récupérer le nom précis du prix (avec usure)
        price_obj = session.query(Price).filter_by(skin_id=input_id, platform="skinport").first()
        search_name = price_obj.market_hash_name if price_obj and price_obj.market_hash_name else (skin_obj.market_hash_name if skin_obj else input_id)
        item_page_url = price_obj.item_page if price_obj and price_obj.item_page else None
        quantity = price_obj.quantity if price_obj else None

        opps.append({
            "input_name": search_name,
            "display_name": skin_obj.name if skin_obj else input_id,
            "item_page": item_page_url,
            "quantity": quantity,
            "roi": o.roi,
            "kontract_score": o.kontract_score,
            "cout_ajuste": o.cout_ajuste
        })

recommender = ActionRecommender()
actions = recommender.generate_action_plan(opps, baskets, [])

if not actions:
    st.info("Aucune action recommandée pour le moment. Lancez un scan ou remplissez vos paniers.")
else:
    # Action Cards
    st.subheader(f"🔥 {len(actions)} Actions Recommandées")
    
    for action in actions:
        with st.container(border=True):
            cols = st.columns([1, 4, 2])
            
            # Badge de type
            type_emoji = {
                ActionType.BUY_NOW: "🛒 ACHETER",
                ActionType.EXECUTE: "🛠️ EXÉCUTER",
                ActionType.SELL_NOW: "💵 VENDRE",
                ActionType.ABANDON: "🛑 ABANDONNER",
                ActionType.BUY_WATCH: "👀 SURVEILLER",
            }.get(action.type, "🔹 INFO")
            
            # Badge de priorité
            priority_color = {
                ActionPriority.URGENT: "red",
                ActionPriority.HIGH: "orange",
                ActionPriority.NORMAL: "blue",
                ActionPriority.LOW: "grey",
            }.get(action.priority, "grey")
            
            cols[0].markdown(f"**{type_emoji}**")
            cols[0].markdown(f":{priority_color}[Priority: {action.priority.value.upper()}]")
            
            cols[1].markdown(f"### {action.opportunity_name if action.opportunity_name else action.market_hash_name}")
            cols[1].write(f"**Pourquoi ?** {action.reason}")
            
            if action.type == ActionType.BUY_NOW:
                unit_price = action.price
                total_cost = unit_price * 10
                cols[2].metric("Prix unitaire (scan)", f"{unit_price:.2f}€", help=f"Coût total × 10 = {total_cost:.2f}€ (prix au moment du scan, peut varier en temps réel)")
                # Stock indicator
                qty = action.quantity
                if qty is not None:
                    if qty >= 20:
                        stock_label = f"🟢 {qty} en stock"
                    elif qty >= 5:
                        stock_label = f"🟡 {qty} en stock"
                    else:
                        stock_label = f"🔴 {qty} en stock (faible)"
                    cols[2].caption(stock_label)
                if action.url:
                    cols[2].link_button("🛒 Voir Listing", action.url, use_container_width=True)
                else:
                    cols[2].button("Voir Listing (URL N/A)", disabled=True, use_container_width=True)
            elif action.type == ActionType.EXECUTE:
                if st.button("Détecter Résultat", key=f"btn_{action.id}", type="primary"):
                    st.write("Lancement du OutputDetector...")

st.divider()
st.subheader("💡 Aide")
st.info("Le plan d'action centralise toutes les décisions. Il priorise les achats urgents et les exécutions de paniers complets.")
