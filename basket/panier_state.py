"""
Module basket/panier_state.py
Gestion de l'état du panier d'inputs (PanierState) et calculs marginaux.

Permet de suivre les achats progressifs pour un trade-up et de calculer
les besoins restants (float, prix) pour atteindre les objectifs.
"""

import logging
from typing import List, Optional, Tuple

from data.database import get_session
from data.models import TradeupBasket, BasketItem, Skin

logger = logging.getLogger(__name__)

class PanierState:
    def __init__(self, basket: TradeupBasket):
        self.basket = basket
        self.items = basket.items
        self.n_total = 5 if self._is_covert() else 10
        self.n_bought = len(self.items)
        self.n_remaining = self.n_total - self.n_bought

    def _is_covert(self) -> bool:
        """Détecte si le trade-up est un Covert (5 inputs)."""
        # On pourrait aussi stocker n_total en BDD
        with get_session() as session:
            skin = session.query(Skin).filter_by(id=self.basket.input_skin_id).first()
            return skin and skin.rarity_id == "rarity_ancient_weapon"

    def get_current_metrics(self) -> dict:
        """Calcule les métriques actuelles du panier."""
        if not self.items:
            return {
                "avg_price": 0.0,
                "avg_float": 0.0,
                "total_cost": 0.0,
                "progress": 0.0
            }
        
        total_price = sum(item.buy_price for item in self.items)
        # On suppose que float_value est normalisé ou on le normalise ici
        total_float = sum(item.float_value or 0.0 for item in self.items)
        
        return {
            "avg_price": total_price / self.n_bought,
            "avg_float": total_float / self.n_bought,
            "total_cost": total_price,
            "progress": (self.n_bought / self.n_total) * 100
        }

    def get_marginal_needs(self, target_avg_float_norm: float = 0.5) -> dict:
        """
        Calcule les besoins pour les prochains items (§4.4.2).
        target_avg_float_norm: l'objectif de float moyen normalisé [0, 1] pour le panier complet.
        """
        if self.n_remaining <= 0:
            return {"status": "completed"}

        # Somme des floats déjà achetés
        sum_bought = sum(item.float_value or 0.5 for item in self.items)
        
        # Somme totale requise pour atteindre la moyenne cible
        sum_required_total = target_avg_float_norm * self.n_total
        
        # Somme restante à combler
        sum_remaining = sum_required_total - sum_bought
        
        # Moyenne requise pour les items restants
        avg_required_remaining = sum_remaining / self.n_remaining
        
        # Bornes réalistes [0, 1]
        avg_required_remaining = max(0.001, min(0.999, avg_required_remaining))

        return {
            "n_remaining": self.n_remaining,
            "required_float_avg": round(avg_required_remaining, 4),
            "target_center": round(avg_required_remaining, 4),
            "margin_error": 0.02 # Tolérance suggérée
        }

def get_or_create_basket(user_id: str, input_skin_id: str, collection_id: str) -> PanierState:
    """Récupère le panier actif ou en crée un nouveau."""
    with get_session() as session:
        basket = session.query(TradeupBasket).filter_by(
            user_id=user_id, 
            input_skin_id=input_skin_id, 
            collection_id=collection_id,
            status="active"
        ).first()
        
        if not basket:
            basket = TradeupBasket(
                user_id=user_id,
                input_skin_id=input_skin_id,
                collection_id=collection_id,
                status="active"
            )
            session.add(basket)
            session.commit()
            session.refresh(basket)
            
        return PanierState(basket)

def add_item_to_basket(basket_id: int, skin_id: str, price: float, float_val: Optional[float] = None):
    """Ajoute un item au panier."""
    with get_session() as session:
        item = BasketItem(
            basket_id=basket_id,
            skin_id=skin_id,
            buy_price=price,
            float_value=float_val
        )
        session.add(item)
        session.commit()
        logger.info(f"Item ajouté au panier {basket_id}: {skin_id} @ {price}€")
