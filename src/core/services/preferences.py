from __future__ import annotations

from datetime import time
from typing import Dict, List, Optional, Set

from src.core.domain.models import (
    POI,
    Coordinates,
    Itinerary,
    MealSlot,
    PreferencesProfile,
    TimeWindow,
)
from src.core.services.dining_and_budget import DiningService

CATEGORY_SYNONYMS: Dict[str, Set[str]] = {
    "Coffee Lover": {"coffee lover", "cafe", "coffee", "cafeteria"},
    "Wine Lover": {"wine lover", "wine_bar", "wine", "winery", "enoteca"},
    "Museum Lover": {"museum lover", "museum", "museu", "art_gallery", "gallery"},
    "Nature Lover": {"nature lover", "park", "parque", "garden", "nature"},
    "Gastronomy & Fine Dining": {
        "gastronomy & fine dining",
        "restaurant",
        "restaurante",
        "fine_dining",
    },
    "Street Food": {"street food", "street_food", "snack", "market"},
}


class PreferencesService:
    """Modula a atratividade de POIs por intensidades (0 a 10) e gera pausas experienciais."""

    def __init__(self) -> None:
        """Inicializar o serviço com o serviço de gastronomia usado nas pausas temáticas."""
        self.dining_service = DiningService()

    def apply_preference_weights(
        self, candidates: List[POI], profile: PreferencesProfile
    ) -> List[POI]:
        """Aplicar o Perfil de Preferência à Pontuação de Utilidade dos candidatos."""
        weighted_list: List[POI] = []
        for poi in candidates:
            intensity = self._match_intensity(poi, profile)
            multiplier = 1.0 + (intensity / 10.0)
            weighted_poi = poi.model_copy(
                update={"utility_score": poi.utility_score * multiplier}
            )
            weighted_list.append(weighted_poi)
        return weighted_list

    def _match_intensity(self, poi: POI, profile: PreferencesProfile) -> float:
        poi_cat = poi.category.lower()
        poi_tags = {poi_cat} | {a.lower() for a in poi.awards}

        max_intensity = profile.get_intensity(poi.category)
        for tag, intensity in profile.intensities.items():
            synonyms = CATEGORY_SYNONYMS.get(tag, {tag.lower()})
            if any(syn in poi_tags or poi_cat in syn for syn in synonyms):
                max_intensity = max(max_intensity, intensity)

        return max_intensity

    def generate_thematic_slots(
        self,
        profile: PreferencesProfile,
        reference_location: Coordinates,
        cafe_candidates: List[POI],
        wine_candidates: List[POI],
        itinerary: Optional[Itinerary] = None,
        departure_location: Optional[Coordinates] = None,
        return_location: Optional[Coordinates] = None,
    ) -> List[MealSlot]:
        """Gerar Slots de Refeição temáticos conforme as intensidades do Perfil de Preferência."""
        slots: List[MealSlot] = []
        dep_loc = departure_location or reference_location
        ret_loc = return_location or reference_location

        if profile.get_intensity("Coffee Lover") >= 5.0:
            c_win = TimeWindow(start_time=time(15, 30), end_time=time(16, 15))
            c_loc = self.dining_service.get_contextual_location_for_slot(
                c_win, dep_loc, ret_loc, itinerary, fallback_to_return=False
            )
            top_cafes = self.dining_service.recommend_meal_places(
                c_loc, cafe_candidates, limit=3
            )
            slots.append(
                MealSlot(
                    id="slot-coffee",
                    name="Pausa para Café",
                    window=c_win,
                    recommended_places=top_cafes,
                    selected_place=top_cafes[0] if top_cafes else None,
                    estimated_cost=35.0,
                )
            )

        if profile.get_intensity("Wine Lover") >= 5.0:
            w_win = TimeWindow(start_time=time(18, 0), end_time=time(19, 15))
            w_loc = self.dining_service.get_contextual_location_for_slot(
                w_win, dep_loc, ret_loc, itinerary, fallback_to_return=True
            )
            top_wine_bars = self.dining_service.recommend_meal_places(
                w_loc, wine_candidates, limit=3
            )
            slots.append(
                MealSlot(
                    id="slot-wine",
                    name="Degustação / Wine Bar",
                    window=w_win,
                    recommended_places=top_wine_bars,
                    selected_place=top_wine_bars[0] if top_wine_bars else None,
                    estimated_cost=120.0,
                )
            )

        return slots
