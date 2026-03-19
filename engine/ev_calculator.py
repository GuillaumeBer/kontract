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
    sell_price: float         # prix de vente attendu (hors frais)
    volume_24h: float = 0.0   # nombre de ventes/jour (liquidité)
    source_sell: str = "skinport"


@dataclass
class EVResult:
    ev_brute: float
    ev_nette: float
    roi: float
    cout_ajuste: float
    pool_size: int
    pool_score: float          # 1 / nb_outputs_total (haut = pool concentré)
    liquidity_score: float     # volume_24h de l'output le plus liquide
    win_prob: float            # prob de tomber sur un output > coût ajusté
    jackpot_ratio: float       # max_price / mean_price — 1.0 = outputs uniformes, >> 1 = jackpot
    ev_ajustee: float          # ev_nette × (win_prob / 100) — gain net pondéré par probabilité
    kontract_score: float      # score composite risk-adjusted (Sharpe-like + bonus liquidité)
    outputs: list[dict] = field(default_factory=list)


def calculate_ev(
    inputs: list[InputSkin],
    outputs_by_collection: dict[str, list[OutputSkin]],
    source_buy: str = "skinport",
    source_sell: str = "skinport",
) -> EVResult:
    """
    Calcule l'EV d'un trade-up de 10 inputs vers les outputs possibles.

    Args:
        inputs: liste de 10 InputSkin (peuvent venir de collections différentes)
        outputs_by_collection: dict collection_id → liste OutputSkin du tier supérieur
        source_buy: "skinport" ou "steam"
        source_sell: "skinport" ou "steam"

    Returns:
        EVResult avec toutes les métriques
    """
    if len(inputs) != 10:
        raise ValueError(f"Un trade-up requiert exactement 10 inputs, reçu {len(inputs)}")

    fee_buy = FEES[source_buy]["buy"]
    fee_sell = FEES[source_sell]["sell"]

    # ÉTAPE 1 — Probabilités selon la composition des 10 inputs
    # Compter combien d'inputs viennent de chaque collection
    collection_counts: dict[str, int] = {}
    for inp in inputs:
        collection_counts[inp.collection_id] = collection_counts.get(inp.collection_id, 0) + 1

    # Construire les probabilités par output
    output_probs: list[tuple[OutputSkin, float]] = []
    for coll_id, count in collection_counts.items():
        coll_outputs = outputs_by_collection.get(coll_id, [])
        if not coll_outputs:
            continue
        coll_prob_weight = count / 10.0
        prob_per_output = coll_prob_weight / len(coll_outputs)
        for out in coll_outputs:
            output_probs.append((out, prob_per_output))

    if not output_probs:
        raise ValueError("Aucun output valide trouvé pour les inputs fournis")

    pool_size = len(output_probs)

    # ÉTAPE 2 — EV brute = Σ(prob_i × prix_vente_output_i)
    ev_brute = sum(prob * out.sell_price for out, prob in output_probs)

    # ÉTAPE 3 — Coût ajusté selon plateforme d'achat
    # Skinport = 5% frais acheteur (on achète à min_price * 1.05)
    # Steam    = 15% frais acheteur
    cout_ajuste = sum(inp.buy_price * (1 + fee_buy) for inp in inputs)

    # ÉTAPE 4 — EV nette après frais de vente
    ev_nette = ev_brute * (1 - fee_sell) - cout_ajuste

    # ÉTAPE 5 — ROI + métriques scoring
    roi = (ev_nette / cout_ajuste) * 100 if cout_ajuste > 0 else 0.0

    pool_score = 1 / pool_size  # haut = pool concentré (différenciateur clé)

    liquidity_score = max(
        (out.volume_24h for out, _ in output_probs), default=0.0
    )

    win_prob = sum(
        prob for out, prob in output_probs
        if out.sell_price * (1 - fee_sell) > cout_ajuste
    )

    # Jackpot ratio — mesure la concentration du risque sur un seul output
    prices = [out.sell_price for out, _ in output_probs]
    max_price = max(prices)
    mean_price = sum(prices) / len(prices)
    jackpot_ratio = max_price / mean_price if mean_price > 0 else 1.0

    # EV ajustée par la probabilité de gagner
    ev_ajustee = ev_nette * (win_prob / 100)

    # Score de risque ajusté (Sharpe-like) + bonus liquidité logarithmique
    score_risque = ev_ajustee / math.sqrt(max(jackpot_ratio, 1.0))
    bonus_liquidite = math.log1p(liquidity_score)
    kontract_score = score_risque * (1 + bonus_liquidite)

    outputs_detail = [
        {
            "skin_id": out.skin_id,
            "name": out.name,
            "sell_price": out.sell_price,
            "prob": round(prob * 100, 2),
            "volume_24h": out.volume_24h,
        }
        for out, prob in sorted(output_probs, key=lambda x: x[0].sell_price, reverse=True)
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
