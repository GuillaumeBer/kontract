"""
Module engine/filters.py
Système de filtrage et scoring des listings Skinport pour les inputs.

Implémente §4.4 de la spécification technique :
  1. Hard Filters (éliminatoires - F1 à F8)
  2. Hybrid Score (soft score 0-100)
  3. Ranking Pipeline
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# --- Configuration & Constantes ---

PREMIUM_PATTERNS = {
    "Case Hardened": ["Blue Gem", "Tier 1", "661"],
    "Fade": ["100%", "99%"],
    "Doppler": ["Ruby", "Sapphire", "Black Pearl", "Emerald"],
}

# --- Utilitaires ---

def has_valuable_sticker(stickers: list[dict]) -> bool:
    """
    Détecte les stickers de valeur (Kato 2014, Crown, etc.).
    Note : Données Skinport simplifiées.
    """
    VALUABLE_KEYWORDS = ["Katowice 2014", "Crown (Foil)", "Howl", "King on the Field"]
    for s in stickers:
        name = s.get("name", "")
        if any(kw in name for kw in VALUABLE_KEYWORDS):
            return True
    return False

def has_premium_pattern(name: str, pattern: Optional[int]) -> bool:
    """
    Détéction simplifiée des patterns premiums.
    """
    for base_name, keywords in PREMIUM_PATTERNS.items():
        if base_name in name:
            # Pour l'instant on se base sur le nom si Skinport l'enrichit
            # En V2 on cross-referencera le pattern ID
            return any(kw.lower() in name.lower() for kw in keywords)
    return False

def build_listing_url(listing: dict) -> str:
    """Construit l'URL vers la page produit Skinport."""
    # Skinport v1 item listings don't always have a direct URL in the JSON?
    # Usually it is https://skinport.com/item/app_id/market_hash_name/asset_id
    market_hash_name = listing.get("market_hash_name", "").replace(" ", "-").replace("|", "-")
    item_id = listing.get("item_id")
    if item_id:
        return f"https://skinport.com/item/cs2/{market_hash_name}/{item_id}"
    return f"https://skinport.com/market?search={listing.get('market_hash_name')}"

# --- Étape 1 : Hard Filters ---

def apply_hard_filters(listing: dict, target: dict) -> tuple[bool, Optional[str]]:
    """
    Retourne (True, None) si le listing passe tous les filtres éliminatoires (§4.4).
    """
    # F1 — Souvenir interdit
    if listing.get("souvenir", False):
        return False, "souvenir_interdit"

    # F2 — Cohérence StatTrak
    if listing.get("stattrak", False) != target.get("stattrak", False):
        return False, "stattrak_incoherent"

    # F3 — Trade lock
    if listing.get("lock_days", 0) > 0:
        return False, f"trade_lock_{listing['lock_days']}j"

    # F4 — Sticker de valeur
    if has_valuable_sticker(listing.get("stickers", [])):
        return False, "sticker_precieux"

    # F5 — Pattern premium
    if has_premium_pattern(listing.get("market_hash_name", ""), listing.get("pattern")):
        return False, "pattern_premium"

    # F6 — Prix aberrant (utilisant la médiane cible)
    median = target.get("median_price", 0)
    price = listing.get("price", 0)
    if median > 0:
        ratio = price / median
        if ratio < 0.5 or ratio > 2.0:
            return False, "prix_aberrant"

    # F7 — Hors budget max input
    max_input = target.get("max_input_price")
    if max_input and price > max_input:
        return False, "hors_budget"

    # F8 — Float hors plage (si spécifié)
    float_val = listing.get("float_value")
    target_min = target.get("float_min")
    target_max = target.get("float_max")
    if float_val is not None:
        if target_min is not None and float_val < target_min:
            return False, "float_trop_bas"
        if target_max is not None and float_val > target_max:
            return False, "float_trop_haut"

    return True, None

# --- Étape 2 : Hybrid Score ---

def calculate_listing_score(listing: dict, target: dict, panier_state: dict) -> dict:
    """
    Score hybride 0–100 pour un listing (§4.4).
    """
    price = listing.get("price", 0)
    median = target.get("median_price", price) or price
    float_val = listing.get("float_value")

    # ── DIMENSION PRIX (40%) ──
    price_saving = (median - price) / median if median > 0 else 0
    price_score = min(1.0, max(0.0, 0.5 + price_saving * 2))
    
    current_avg = panier_state.get("avg_price", median)
    marginal_gain = (current_avg - price) / current_avg if current_avg > 0 else 0
    marginal_price_score = min(1.0, max(0.0, 0.5 + marginal_gain * 3))
    
    prix_final = 0.65 * price_score + 0.35 * marginal_price_score

    # ── DIMENSION FLOAT (35%) ──
    if float_val is not None:
        # On calcule le float normalisé [0, 1] si les min/max du skin sont fournis
        f_min = target.get("skin_float_min", 0.0)
        f_max = target.get("skin_float_max", 1.0)
        float_norm = (float_val - f_min) / (f_max - f_min) if f_max > f_min else 0
        
        # Cible demandée (marginal float remaining)
        req_center = panier_state.get("required_float_norm_center", 0.5)
        marginal_float_score = max(0.0, 1.0 - abs(float_norm - req_center))
        
        float_final = marginal_float_score
    else:
        float_final = 0.7  # Neutre

    # ── DIMENSION QUALITÉ (15%) ──
    sticker_count = len(listing.get("stickers", []))
    sticker_score = 1.0 if sticker_count == 0 else max(0.5, 1.0 - sticker_count * 0.1)
    
    # Homogénéité (V1 simplifiée : bonus si float proche du centre)
    qualite_final = sticker_score 

    # ── DIMENSION DISPONIBILITÉ (10%) ──
    age_min = listing.get("age_minutes", 60)
    freshness = max(0.0, 1.0 - age_min / 120)
    dispo_final = freshness

    # ── SCORE FINAL ──
    score = (
        0.40 * prix_final +
        0.35 * float_final +
        0.15 * qualite_final +
        0.10 * dispo_final
    ) * 100

    return {
        "score": round(score, 1),
        "prix_score": round(prix_final * 100, 1),
        "float_score": round(float_final * 100, 1),
        "url": build_listing_url(listing),
        "recommended": score >= 60,
    }

# --- Pipeline ---

def rank_input_listings(
    raw_listings: list[dict],
    target: dict,
    panier_state: dict,
    top_n: int = 5
) -> dict:
    """
    Pipeline complet : filtre → score → classement.
    """
    rejected = []
    candidates = []

    for listing in raw_listings:
        passed, reason = apply_hard_filters(listing, target)
        if passed:
            candidates.append(listing)
        else:
            rejected.append({"listing": listing, "reason": reason})

    scored = []
    for listing in candidates:
        result = calculate_listing_score(listing, target, panier_state)
        scored.append({**listing, **result})

    ranked = sorted(scored, key=lambda x: x["score"], reverse=True)

    # Récapitulatif des rejets
    rejection_summary = {}
    for r in rejected:
        reason = r["reason"]
        rejection_summary[reason] = rejection_summary.get(reason, 0) + 1

    return {
        "top_listings": ranked[:top_n],
        "total_available": len(raw_listings),
        "passed_filters": len(candidates),
        "rejected": len(rejected),
        "rejection_summary": rejection_summary,
        "best_score": ranked[0]["score"] if ranked else 0,
    }
