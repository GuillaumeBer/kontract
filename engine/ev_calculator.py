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

# Frais par plateforme
FEES = {
    "skinport": {"buy": 0.05, "sell": 0.03},
    "steam":    {"buy": 0.15, "sell": 0.15},
}


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
    sell_price: float         # prix "spot" actuel
    volume_24h: float = 0.0
    volume_7d: float = 0.0
    volume_30d: float = 0.0
    median_7d: float = None
    median_30d: float = None
    source_sell: str = "skinport"


@dataclass
class EVResult:
    ev_brute: float
    ev_nette: float
    roi: float
    cout_ajuste: float
    pool_size: int
    pool_score: float
    liquidity_score: float
    win_prob: float
    jackpot_ratio: float
    ev_ajustee: float
    kontract_score: float
    price_reliability: str = "low"  # "high" | "medium" | "low"
    outputs: list[dict] = field(default_factory=list)


def calculate_ev(
    inputs: list[InputSkin],
    outputs_by_collection: dict[str, list[OutputSkin]],
    source_buy: str = "skinport",
    source_sell: str = "skinport",
    min_vol_7d: int = 7,  # Nouveau paramètre pour la fiabilité
) -> EVResult:
    """
    Calcule l'EV avec logique de fallback sur les prix de vente et redistribution.
    """
    if len(inputs) != 10:
        raise ValueError(f"Un trade-up requiert exactement 10 inputs, reçu {len(inputs)}")

    fee_buy = FEES[source_buy]["buy"]
    fee_sell = FEES[source_sell]["sell"]

    # ÉTAPE 1 — Probabilités initiales par collection
    collection_counts: dict[str, int] = {}
    for inp in inputs:
        collection_counts[inp.collection_id] = collection_counts.get(inp.collection_id, 0) + 1

    # ÉTAPE 2 — Détermination des prix de vente réels et filtrage des outputs
    processed_outputs: list[tuple[OutputSkin, float, str]] = []  # (skin, prob_initiale, reliability)
    
    for coll_id, count in collection_counts.items():
        coll_outputs = outputs_by_collection.get(coll_id, [])
        if not coll_outputs:
            continue
            
        coll_prob_weight = count / 10.0
        
        # Évaluer la fiabilité et le prix de chaque output de cette collection
        valid_coll_outputs = []
        for out in coll_outputs:
            price = None
            reliability = "insufficient"
            
            if out.volume_7d and out.volume_7d >= min_vol_7d and out.median_7d:
                price = out.median_7d
                reliability = "high"
            elif out.volume_30d and out.volume_30d >= 15 and out.median_30d:
                price = out.median_30d
                reliability = "medium"
            elif out.sell_price and out.sell_price > 0:
                price = out.sell_price
                reliability = "low"
            
            if price is not None:
                valid_coll_outputs.append((out, price, reliability))
        
        if not valid_coll_outputs:
            continue
            
        # Redistribution des probabilités au sein de la collection
        prob_per_output = coll_prob_weight / len(valid_coll_outputs)
        for out_obj, price, rel in valid_coll_outputs:
            # On stocke le prix calculé dans l'objet pour l'EV brute
            out_obj.sell_price = price
            processed_outputs.append((out_obj, prob_per_output, rel))

    if not processed_outputs:
        raise ValueError("Aucun output valide après filtrage de fiabilité")

    # Fiabilité globale = le pire cas parmi les outputs
    reliability_ranks = {"high": 3, "medium": 2, "low": 1}
    min_rank = min(reliability_ranks[rel] for _, _, rel in processed_outputs)
    overall_reliability = [k for k, v in reliability_ranks.items() if v == min_rank][0]

    pool_size = len(processed_outputs)

    # ÉTAPE 3 — EV brute = Σ(prob_i × prix_vente_redistribué_i)
    ev_brute = sum(prob * out.sell_price for out, prob, _ in processed_outputs)

    # ÉTAPE 4 — Coût ajusté
    cout_ajuste = sum(inp.buy_price * (1 + fee_buy) for inp in inputs)

    # ÉTAPE 5 — EV nette
    ev_nette = ev_brute * (1 - fee_sell) - cout_ajuste
    roi = (ev_nette / cout_ajuste) * 100 if cout_ajuste > 0 else 0.0

    pool_score = 1 / pool_size
    liquidity_score = max((out.volume_7d or 0 for out, _, _ in processed_outputs), default=0.0) / 7.0 # normalisé / 7j

    win_prob = sum(
        prob for out, prob, _ in processed_outputs
        if out.sell_price * (1 - fee_sell) > cout_ajuste
    )

    prices = [out.sell_price for out, _, _ in processed_outputs]
    max_price = max(prices)
    mean_price = sum(prices) / len(prices)
    jackpot_ratio = max_price / mean_price if mean_price > 0 else 1.0

    ev_ajustee = ev_nette * win_prob # win_prob est entre 0 et 1 ici après sum(prob)

    # Score composite
    score_risque = ev_ajustee / math.sqrt(max(jackpot_ratio, 1.0))
    bonus_liquidite = math.log1p(liquidity_score)
    kontract_score = score_risque * (1 + bonus_liquidite)

    outputs_detail = [
        {
            "skin_id": out.skin_id,
            "name": out.name,
            "sell_price": out.sell_price,
            "prob": round(prob * 100, 2),
            "reliability": rel,
            "volume_7d": out.volume_7d,
        }
        for out, prob, rel in sorted(processed_outputs, key=lambda x: x[0].sell_price, reverse=True)
    ]

    return EVResult(
        ev_brute=round(ev_brute, 4),
        ev_nette=round(ev_nette, 4),
        roi=round(roi, 2),
        cout_ajuste=round(cout_ajuste, 4),
        pool_size=pool_size,
        pool_score=round(pool_score, 4),
        liquidity_score=round(liquidity_score, 2),
        win_prob=round(win_prob * 100, 2),
        jackpot_ratio=round(jackpot_ratio, 2),
        ev_ajustee=round(ev_ajustee, 4),
        kontract_score=round(kontract_score, 4),
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
