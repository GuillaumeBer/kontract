import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data.database import get_session
from data.models import PandL

st.title("📈 Analyse P&L et Performances")
st.caption("Suivi historique des trade-ups exécutés.")

with get_session() as session:
    history = session.query(PandL).order_by(PandL.created_at.desc()).all()
    
    if not history:
        st.info("Aucun historique P&L pour le moment. Voici une simulation (mock) :")
        # Generate mock data for demonstration
        dates = [datetime.now() - timedelta(days=i) for i in range(10, 0, -1)]
        mock_data = pd.DataFrame({
            "Date": dates,
            "P&L (€)": [1.5, -0.4, 2.8, 1.2, -5.0, 3.5, 0.8, -1.2, 4.2, 2.5],
            "ROI (%)": [15, -4, 28, 12, -25, 35, 8, -6, 22, 18],
            "EV Error (%)": [2, 5, -1, 3, 15, 2, 4, -5, 1, 3]
        })
        
        c1, c2, c3 = st.columns(3)
        c1.metric("P&L Total", f"{mock_data['P&L (€)'].sum():.2f}€", "+12.4€")
        c2.metric("ROI Moyen", f"{mock_data['ROI (%)'].mean():.1f}%")
        c3.metric("Précision EV", f"{100 - mock_data['EV Error (%)'].abs().mean():.1f}%")

        st.divider()
        st.subheader("Courbe P&L Cumulé")
        mock_data["Cumul (€)"] = mock_data["P&L (€)"].cumsum()
        st.area_chart(mock_data.set_index("Date")["Cumul (€)"])
        
        st.subheader("Historique des sessions")
        st.dataframe(mock_data, use_container_width=True, hide_index=True)
    else:
        # Real data processing
        df = pd.DataFrame([
            {
                "Date": p.created_at,
                "P&L (€)": p.p_and_l_euro,
                "ROI (%)": p.p_and_l_percent,
                "Coût": p.total_cost,
                "Précision EV": f"{100 - abs(p.ev_error_percent):.1f}%"
            }
            for p in history
        ])
        
        c1, c2, c3 = st.columns(3)
        c1.metric("P&L Total", f"{df['P&L (€)'].sum():.2f}€")
        c2.metric("ROI Moyen", f"{df['ROI (%)'].mean():.1f}%")
        c3.metric("Nombre de Sessions", len(df))

        st.divider()
        st.subheader("Evolution du Capital")
        df["Cumul (€)"] = df["P&L (€)"].cumsum()
        st.area_chart(df.set_index("Date")["Cumul (€)"])
        
        st.dataframe(df, use_container_width=True, hide_index=True)
