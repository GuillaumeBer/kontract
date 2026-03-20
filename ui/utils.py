import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from data.database import get_session, redis_client
from data.models import Price

def get_last_price_update() -> str:
    with get_session() as session:
        latest = session.query(Price).order_by(Price.updated_at.desc()).first()
        if latest and latest.updated_at:
            dt = latest.updated_at
            if hasattr(dt, 'strftime'):
                return dt.strftime("%H:%M:%S")
    return "Jamais"

def apply_custom_css():
    st.markdown("""
        <style>
        .stMetric {
            background-color: #f0f2f6;
            padding: 10px;
            border-radius: 10px;
        }
        .main-header {
            font-size: 2.5rem;
            font-weight: 700;
            color: #1E1E1E;
            margin-bottom: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)

def color_ks(val):
    if val >= 0.5:
        return "background-color: #1a472a; color: white"
    elif val >= 0.2:
        return "background-color: #2d6a4f; color: white"
    elif val >= 0.1:
        return "background-color: #74c69d"
    return ""

def color_roi(val):
    if val >= 50:
        return "background-color: #1a472a; color: white"
    elif val >= 20:
        return "background-color: #2d6a4f; color: white"
    elif val >= 10:
        return "background-color: #74c69d"
    return ""

def color_win(val):
    if val >= 100:
        return "background-color: #1a472a; color: white"
    elif val >= 80:
        return "background-color: #2d6a4f; color: white"
    elif val >= 50:
        return "background-color: #74c69d"
    return ""

def color_rel(val):
    if "STABLE" in val or "TRENDING_UP" in val:
        return "color: #2d6a4f; font-weight: bold"
    elif "TRENDING_DOWN" in val:
        return "color: #d1a110; font-weight: bold"
    return "color: #b91c1c; font-weight: bold"


@st.fragment(run_every=1)
def render_header(title: str):
    """Affiche le titre et le timer en temps réel (§4.12)."""
    st.title(title)
    last_update = get_last_price_update()
    next_up = get_next_update_timer()
    st.caption(f"Dernière mise à jour : {last_update} | Prochain scan dans : {next_up}")


def get_next_update_timer() -> str:
    """Calcul du temps restant avant le prochain scan (§4.12)."""
    last_start_str = None
    
    if redis_client:
        last_start_str = redis_client.get("scan:last_start")
    
    # Fallback fichier si Redis est absent
    if not last_start_str and os.path.exists("scan_status.json"):
        try:
            with open("scan_status.json", "r") as f:
                data = json.load(f)
                last_start_str = data.get("last_start")
        except Exception:
            pass

    if not last_start_str:
        return "Prêt"
        
    try:
        last_start = datetime.fromisoformat(last_start_str)
        next_start = last_start + timedelta(minutes=5)
        remaining = next_start - datetime.now()
        
        if remaining.total_seconds() <= 0:
            return "Imminent..."
            
        mins, secs = divmod(int(remaining.total_seconds()), 60)
        return f"{mins:02d}:{secs:02d}"
    except Exception:
        return "Err"
