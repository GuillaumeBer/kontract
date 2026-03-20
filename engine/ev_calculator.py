"""
Module engine/ev_calculator.py
Calcule l'Expected Value (EV) d'un trade-up contract CS2.

Formule EV en 5 étapes (spec §4.3) :
  1. Probabilités selon composition des 10 inputs
  2. EV brute = Σ(prob_i × prix_vente_output_i)
  3. Coût ajusté selon plateforme d'achat (frais acheteur)
  4. EV nette après frais de vente
  5. ROI + métriques scoring
"""

import math
from dataclasses import dataclass, field
from engine.momentum import PriceSignalEngine

# Frais par plateforme (spec §4.3 — centralisés et versionnés)
# Skinport : frais acheteur = 0% (prix affiché = prix payé), 3% côté vendeur
# Steam    : prix affiché inclut déjà les 15% vendeur — 0% frais acheteur supplémentaires
FEES = {
    "skinport": {"buy": 0.00, "sell": 0.03},
    "steam":    {"buy": 0.00, "sell": 0.15},
}


@dataclass
class SellPriceResult:
    adjusted_price: float
    reliability: str  # "stable" | "trending_down" | "trending_up" | "*_price_divergence"


def get_sell_price(price_data: dict, steam_data: dict | None = None) -> "SellPriceResult | None":
    """
    Calcule le prix de vente ajusté selon 4 règles (spec §4.3).
    Retourne None si données insuffisantes (< 30 ventes sur toutes les fenêtres).

    Règle 1 — Fenêtre adaptative : médiane 7j si volume_7j ≥ 30, sinon médiane 30j, sinon exclu.
    Règle 2 — Tendance : trend = (avg_7d - avg_30d) / avg_30d (seulement si fenêtre 7j active).
    Règle 3 — Ajustement conservateur : pénalité 50% si baisse > 15%, inchangé si hausse.
    Règle 4 — Cross-check Steam (V1+) : min(adjusted, steam_median) si divergence > 20%.
    """
    volume_7d  = price_data.get("volume_7d")  or 0
    volume_30d = price_data.get("volume_30d") or 0
    median_7d  = price_data.get("median_7d")
    median_30d = price_data.get("median_30d")
    avg_7d     = price_data.get("avg_7d")
    avg_30d    = price_data.get("avg_30d")

    # Règle 1 — Fenêtre adaptative (seuil absolu : 30 ventes)
    if volume_7d >= 30 and median_7d:
        base_price = median_7d
        # Règle 2 — Détection de tendance (seulement si données avg disponibles)
        if avg_7d and avg_30d and avg_30d > 0:
            trend = (avg_7d - avg_30d) / avg_30d
        else:
            trend = 0.0
    elif volume_30d >= 30 and median_30d:
        base_price = median_30d
        trend = 0.0  # pas de données 7j pour détecter une tendance fiable
    else:
        return None  # insufficient_data → exclu du scan

    # Règle 3 — Ajustement conservateur
    if trend < -0.15:
        # Pénalité partielle à 50% — on anticipe sans projeter linéairement
        adjusted_price = base_price * (1 + trend * 0.5)
        reliability = "trending_down"
    elif trend > 0.15:
        # Pas de surpondération haussière
        adjusted_price = base_price
        reliability = "trending_up"
    else:
        adjusted_price = base_price
        reliability = "stable"

    # Règle 4 — Cross-check multi-sources (V1+)
    if steam_data and steam_data.get("median") and adjusted_price > 0:
        divergence = abs(adjusted_price - steam_data["median"]) / adjusted_price
        if divergence > 0.20:
            adjusted_price = min(adjusted_price, steam_data["median"])
            reliability += "_price_divergence"

    return SellPriceResult(
        adjusted_price=round(adjusted_price, 4),
        reliability=reliability,
    )


def detect_pump(out: "OutputSkin") -> float:
    """
    Detects potential price manipulation (Spec §4.7.2).
    Returns a pump_score (0-1), where 1.0 is a definite pump.
    """
    if not out.avg_7d or out.avg_7d <= 0 or not out.avg_24h:
        return 0.0

    # Increase > 50% in 24h vs 7d average
    price_jump = (out.avg_24h - out.avg_7d) / out.avg_7d
    
    # Low liquidity makes it easier to pump
    low_liq = 1.0 if (out.volume_7d or 0) < 15 else 0.5 if (out.volume_7d or 0) < 30 else 0.0
    
    if price_jump > 0.50:
        return 1.0 * low_liq
    elif price_jump > 0.25:
        return 0.5 * low_liq
    
    return 0.0


def get_doppler_ev(base_price: float, skin_name: str) -> float:
    """
    Weighted average price for Dopplers (Spec §4.7).
    Weights: P1-P4 (98% combined), Ruby/Sapphire (1.5%), Emerald/Black Pearl (0.5%).
    Simplified for MVP: +15% premium to median price to account for rare phases.
    """
    if "Doppler" in skin_name:
        return base_price * 1.15
    return base_price


@dataclass
class InputSkin:
    skin_id: str
    name: str
    collection_id: str
    rarity_id: str
    buy_price: float          # prix d'achat (hors frais)
    source_buy: str = "skinport"


@dataclass
class OutputSkin:
    skin_id: str
    name: str
    sell_price: float          # prix spot (brut Skinport) — ajusté en interne par calculate_ev
    volume_24h: float = 0.0
    volume_7d: float = 0.0
    volume_30d: float = 0.0
    median_24h: float = None
    median_7d: float = None
    median_30d: float = None
    median_90d: float = None
    avg_24h: float = None
    avg_7d: float = None
    avg_30d: float = None
    avg_90d: float = None
    source_sell: str = "skinport"
    reliability: str = "stable"  # "stable" | "trending_down" | "trending_up" | "medium" | "low"


@dataclass
class EVResult:
    ev_brute: float
    ev_nette: float
    roi: float
    cout_ajuste: float
    pool_size: int
    nb_valid_outputs: int  # outputs avec prix fiable (après redistribution)
    pool_score: float
    liquidity_score: float
    win_prob: float
    cv_pond: float         # coeff. de variation pondéré par probabilité (remplace jackpot_ratio)
    ev_ajustee: float      # EV nette × win_prob (conservé pour affichage, non utilisé dans le score)
    floor_ratio: float     # min(prix_outputs) × (1 - frais_vente) / cout_ajuste
    kontract_score: float
    high_volatility: bool = False   # True si ≥1 output avec variation 24h > 15% vs avg_7d
    pump_score: float = 0.0         # 0.0 - 1.0 (signaux de manipulation)
    momentum_score: float = 0.5     # 0.0 - 1.0
    momentum_multiplier: float = 1.0
    kelly_criterion: float = 0.0     # % suggéré d'allocation
    price_reliability: str = "low"  # "high" | "medium" | "low"
    outputs: list[dict] = field(default_factory=list)


def calculate_ev(
    inputs: list[InputSkin],
    outputs_by_collection: dict[str, list[OutputSkin]],
    source_buy: str = "skinport",
    source_sell: str = "skinport",
    min_vol_7d: int = 30,
    exclude_trending_down: bool = False,
    exclude_high_volatility: bool = False,
    input_trend: float = 0.0,        # (avg_24h - avg_7d) / avg_7d des inputs — détection recipe velocity
    input_liquidity_status: str = "liquid",  # "liquid" | "partial" | "scarce" — §4.5
    vol_24h_input: float = 0.0,      # volume 24h de l'input — §4.6 input_speed_bonus
    collection_active: bool = True,  # S1 momentum signal
) -> EVResult:
    """
    Calcule l'EV avec fallback sur les prix, détection de tendance et redistribution.

    Logique de fiabilité par output (spec §4.3) :
      - volume_7d ≥ min_vol_7d + median_7d → "high" (avec détection tendance si avg disponibles)
      - volume_30d ≥ 15 + median_30d       → "medium"
      - sell_price spot disponible          → "low"
      - aucune donnée                       → exclu, probabilité redistribuée aux autres outputs
    """
    if len(inputs) not in (5, 10):
        raise ValueError(f"Un trade-up requiert 5 ou 10 inputs, reçu {len(inputs)}")

    fee_buy = FEES[source_buy]["buy"]
    fee_sell = FEES[source_sell]["sell"]

    n_inputs = len(inputs)

    # ÉTAPE 1 — Probabilités initiales par collection
    collection_counts: dict[str, int] = {}
    for inp in inputs:
        collection_counts[inp.collection_id] = collection_counts.get(inp.collection_id, 0) + 1

    # ÉTAPE 2 — Détermination des prix de vente, détection tendance et redistribution
    processed_outputs: list[tuple[OutputSkin, float, str]] = []  # (skin, prob, reliability)

    for coll_id, count in collection_counts.items():
        coll_outputs = outputs_by_collection.get(coll_id, [])
        if not coll_outputs:
            continue

        coll_prob_weight = count / n_inputs

        # Évaluer fiabilité et prix ajusté de chaque output (avec fallback + tendance)
        valid_coll_outputs = []
        for out in coll_outputs:
            price = None
            reliability = "insufficient"

            # 1. Sélection de la fenêtre (§4.3 adaptive windows)
            if out.volume_7d and out.volume_7d >= min_vol_7d and out.median_7d:
                price = out.median_7d
                reliability = "high"
            elif out.volume_30d and out.volume_30d >= min_vol_7d and out.median_30d:
                price = out.median_30d
                reliability = "medium"
            elif out.avg_90d and out.avg_90d > 0:
                price = out.avg_90d
                reliability = "low"
            elif out.sell_price and out.sell_price > 0:
                price = out.sell_price
                reliability = "low"

            if price:
                # 2. Cap conservateur (§4.6 — ne pas surestimer si le spot est plus bas)
                if out.sell_price and out.sell_price < price:
                    price = out.sell_price

                # 3. Détection de tendance et malus (§4.6)
                if out.avg_7d and out.avg_30d and out.avg_30d > 0:
                    trend = (out.avg_7d - out.avg_30d) / out.avg_30d
                    if trend < -0.15:
                        price = price * (1 + trend * 0.5)
                        reliability += "_trending_down"
                    elif trend > 0.15:
                        reliability += "_trending_up"
                    else:
                        reliability += "_stable"
                else:
                    reliability += "_stable"

                # 4. Doppler specialized weighting
                price = get_doppler_ev(price, out.name)

            if price is None:
                continue  # exclu (données absentes) — sa probabilité est redistribuée

            if exclude_trending_down and "trending_down" in reliability:
                # Si on demande d'exclure les tendances baissières, on rejette tout le trade-up (§4.7.1)
                raise ValueError("trending_down_excluded")

            # Étape 2b — Pénalité haute volatilité 24h (spec §4.3)
            # Si la variation 24h dépasse 15% vs la moyenne 7j → prix × 0.85
            if out.avg_7d and out.avg_7d > 0 and out.avg_24h:
                if abs(out.avg_24h - out.avg_7d) / out.avg_7d > 0.15:
                    if exclude_high_volatility:
                        raise ValueError("high_volatility_excluded")
                    price *= 0.85
                    reliability = reliability + "_high_volatility"

            # Étape 2c — Pump detection
            pump_val = detect_pump(out)
            if pump_val > 0.7:
                reliability += "_pump_detected"
                price *= 0.7  # Strong haircut for potential manipulation

            valid_coll_outputs.append((out, price, reliability, pump_val))

        if not valid_coll_outputs:
            continue

        # Redistribution des probabilités au sein de la collection
        prob_per_output = coll_prob_weight / len(valid_coll_outputs)
        for out_obj, price, rel, p_val in valid_coll_outputs:
            out_obj.sell_price = price
            processed_outputs.append((out_obj, prob_per_output, rel, p_val))

    if not processed_outputs:
        raise ValueError("Aucun output valide après filtrage de fiabilité")

    # Fiabilité globale = le pire cas parmi les outputs
    def _rel_rank(rel: str) -> int:
        # Normaliser : retirer les suffixes secondaires (_high_volatility, _price_divergence)
        base = rel.replace("_high_volatility", "").replace("_price_divergence", "").rstrip("_")
        if base in ("stable", "trending_up"):
            return 3
        if base in ("medium", "trending_down"):
            return 2
        return 1  # "low"

    min_rank = min(_rel_rank(rel) for _, _, rel, _ in processed_outputs)
    overall_reliability = {3: "high", 2: "medium", 1: "low"}[min_rank]

    pool_size = len(processed_outputs)
    nb_valid_outputs = pool_size

    # ÉTAPE 3 — EV brute = Σ(prob_i × prix_vente_redistribué_i)
    ev_brute = sum(prob * out.sell_price for out, prob, _, _ in processed_outputs)

    # ÉTAPE 4 — Coût ajusté (spec §4.3 : frais acheteur s'*ajoutent* au prix, (1 + fee_buy))
    cout_ajuste = sum(inp.buy_price * (1 + fee_buy) for inp in inputs)

    # ÉTAPE 5 — EV nette
    ev_nette = ev_brute * (1 - fee_sell) - cout_ajuste
    roi = (ev_nette / cout_ajuste) * 100 if cout_ajuste > 0 else 0.0

    pool_score = 1 / pool_size

    # Liquidité output pondérée par probabilité (spec §4.6 — remplace max())
    liquidity_score = sum(
        prob * (out.volume_7d or 0) for out, prob, _, _ in processed_outputs
    ) / 7.0

    # win_prob sur prix NET après frais (spec §4.6 Étape 1 — corrigé)
    win_prob = sum(
        prob for out, prob, _, _ in processed_outputs
        if out.sell_price * (1 - fee_sell) > cout_ajuste
    )

    ev_ajustee = ev_nette * win_prob

    # ── Coefficient de variation pondéré (spec §4.6 — remplace jackpot_ratio) ──
    mean_pond = sum(prob * out.sell_price for out, prob, _, _ in processed_outputs)
    var_pond  = sum(prob * (out.sell_price - mean_pond) ** 2 for out, prob, _, _ in processed_outputs)
    cv_pond   = math.sqrt(var_pond) / mean_pond if mean_pond > 0 else 1.0

    # ── Floor ratio (spec §4.6 — protection pire outcome) ──
    min_output_price = min(out.sell_price for out, _, _, _ in processed_outputs)
    floor_ratio = (min_output_price * (1 - fee_sell)) / cout_ajuste if cout_ajuste > 0 else 0.0
    floor_factor = 1.0 if floor_ratio >= 0.20 else (0.5 + floor_ratio * 2.5)

    # ── Détection haute volatilité 24h (spec §4.3 Étape 2b) ──
    # La pénalité × 0.85 sur le prix a déjà été appliquée par output dans la boucle ci-dessus.
    # On lève ici le flag global pour le score et l'affichage.
    high_volatility = any("_high_volatility" in rel for _, _, rel, _ in processed_outputs)
    pump_score = max(p_val for _, _, _, p_val in processed_outputs) if processed_outputs else 0.0
    volatility_factor = 0.70 if high_volatility or pump_score > 0.5 else 1.00

    # ── Recipe velocity penalty (spec §4.7) ──
    # input_trend = (avg_24h_inputs - avg_7d_inputs) / avg_7d_inputs
    # Si les inputs montent > 10% en 24h, le trade-up est probablement en train d'être saturé.
    velocity_penalty = max(0.5, 1.0 - input_trend) if input_trend > 0.10 else 1.0

    # ── Trade hold discount (spec §4.6) ──
    # 7 jours de hold sur Skinport/Steam → coût d'opportunité 0.5%/j
    hold_discount = max(0.5, 1.0 - 0.005 * 7)  # = 0.965

    # ── Exécutabilité inputs (spec §4.6) ──
    input_exec_factor = {
        "liquid":  1.00,
        "partial": 0.75,
        "scarce":  0.40,
    }.get(input_liquidity_status, 0.40)

    # ── Vitesse d'exécution inputs (spec §4.6) ──
    input_speed_bonus = math.log1p(vol_24h_input)

    # ── Price Signal Momentum (spec §4.7.2) ──
    pse = PriceSignalEngine()
    momentum_data = pse.compute_momentum_score(collection_active)
    momentum_multiplier = momentum_data["multiplier"]

    # ── Kontract Score v4 complet (spec §4.6) ──
    bonus_liquidite = math.log1p(liquidity_score)
    kontract_score = (
        (ev_nette / math.sqrt(max(cv_pond, 0.01)))
        * floor_factor
        * (1 + bonus_liquidite)
        * hold_discount
        * input_exec_factor
        * (1 + 0.15 * input_speed_bonus)
        * velocity_penalty
        * volatility_factor
        * momentum_multiplier
    )

    # ── Kelly Criterion (spec §4.6) ──
    # Formula: K = W - (1 - W) / (ROI/100)
    if roi > 0 and win_prob > 0:
        b_ratio = roi / 100
        kelly = win_prob - (1 - win_prob) / b_ratio
        kelly_criterion = max(0.0, kelly * 100) # En %
    else:
        kelly_criterion = 0.0

    # ev_ajustee conservé pour affichage (win_prob en %) mais pas dans la formule du score
    ev_ajustee = ev_nette * win_prob

    outputs_detail = [
        {
            "skin_id": out.skin_id,
            "name": out.name,
            "sell_price": out.sell_price,
            "prob": round(prob * 100, 2),
            "reliability": rel,
            "volume_7d": out.volume_7d,
            "median_24h": out.median_24h,
            "median_7d": out.median_7d,
            "median_30d": out.median_30d,
            "median_90d": out.median_90d,
            "avg_24h": out.avg_24h,
            "avg_7d": out.avg_7d,
            "avg_30d": out.avg_30d,
            "avg_90d": out.avg_90d,
        }
        for out, prob, rel, p_val in sorted(processed_outputs, key=lambda x: x[0].sell_price, reverse=True)
    ]

    return EVResult(
        ev_brute=round(ev_brute, 4),
        ev_nette=round(ev_nette, 4),
        roi=round(roi, 2),
        cout_ajuste=round(cout_ajuste, 4),
        pool_size=pool_size,
        nb_valid_outputs=nb_valid_outputs,
        pool_score=round(pool_score, 4),
        liquidity_score=round(liquidity_score, 2),
        win_prob=round(win_prob * 100, 2),
        cv_pond=round(cv_pond, 4),
        ev_ajustee=round(ev_ajustee, 4),
        floor_ratio=round(floor_ratio, 4),
        kontract_score=round(kontract_score, 4),
        high_volatility=high_volatility,
        pump_score=round(pump_score, 2),
        momentum_score=momentum_data["momentum_score"],
        momentum_multiplier=momentum_multiplier,
        kelly_criterion=round(kelly_criterion, 1),
        price_reliability=overall_reliability,
        outputs=outputs_detail,
    )


if __name__ == "__main__":
    # Test avec des données fictives cohérentes
    print("Test EV calculator avec données fictives...\n")

    # Exemple : 10 inputs Mil-Spec (bleu) de la même collection → outputs Restricted (violet)
    from engine.ev_calculator import InputSkin, OutputSkin, calculate_ev

    inputs = [
        InputSkin("skin-1", "AK-47 | Blue Laminate", "col-1", "rarity_rare_weapon", buy_price=1.50)
        for _ in range(10)
    ]

    outputs = {
        "col-1": [
            OutputSkin("skin-out-1", "AK-47 | Redline (FT)", sell_price=40.0, volume_24h=50),
            OutputSkin("skin-out-2", "M4A4 | X-Ray (FT)", sell_price=15.0, volume_24h=20),
            OutputSkin("skin-out-3", "AWP | Corticera (FT)", sell_price=8.0, volume_24h=5),
        ]
    }

    result = calculate_ev(inputs, outputs)
    print(f"Coût ajusté (10 inputs + 5% frais) : {result.cout_ajuste:.2f} €")
    print(f"EV brute                           : {result.ev_brute:.2f} €")
    print(f"EV nette (après 3% frais vente)    : {result.ev_nette:.2f} €")
    print(f"ROI                                : {result.roi:.1f}%")
    print(f"Pool size                          : {result.pool_size}")
    print(f"Pool score                         : {result.pool_score:.4f}")
    print(f"Liquidité (vol 24h max output)     : {result.liquidity_score}")
    print(f"Win probability                    : {result.win_prob:.1f}%")
    print("\nOutputs possibles :")
    for o in result.outputs:
        print(f"  {o['name']}: {o['prob']}% de chance, prix vente {o['sell_price']} €")
