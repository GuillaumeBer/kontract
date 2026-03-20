import streamlit as st
from data.database import init_db

# Initialisation BDD
init_db()

st.set_page_config(
    page_title="Kontract.gg — CS2 Trade-Up Suite",
    page_icon="🎯",
    layout="wide",
)

# Configuration de la navigation (Spec §4.14)
pg = st.navigation([
    st.Page("pages/plan.py", title="Plan d'Action", icon="📋"),
    st.Page("pages/scanner.py", title="Scanner EV", icon="🔍"),
    st.Page("pages/portfolio.py", title="Portefeuille", icon="💼"),
    st.Page("pages/calculateur.py", title="Calculateur", icon="🧮"),
    st.Page("pages/pl.py", title="Analyse P&L", icon="📈"),
])

pg.run()
