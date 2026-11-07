from __future__ import annotations

from datetime import time
from typing import List

from src.core.domain.models import POI, Coordinates, MealSlot, PreferencesProfile, TimeWindow
from src.core.services.dining_and_budget import DiningService


class PreferencesService:
    """Modula a atratividade de POIs por intensidades (0 a 10) e gera pausas experienciais."""

    def __init__(self) -> None:
        self.dining_service = DiningService()

    def apply_preference_weights(
        self, candidates: List[POI], profile: PreferencesProfile
    ) -> List[POI]:
        weighted_list: List[POI] = []
        for poi in candidates:
            intensity = profile.get_intensity(poi.category)
            multiplier = 1.0 + (intensity / 10.0)
            weighted_poi = poi.model_copy(
                update={"utility_score": poi.utility_score * multiplier}
            )
            weighted_list.append(weighted_poi)
        return weighted_list

    def generate_thematic_slots(
        self,
        profile: PreferencesProfile,
        reference_location: Coordinates,
        cafe_candidates: List[POI],
        wine_candidates: List[POI],
    ) -> List[MealSlot]:
        slots: List[MealSlot] = []

        # Coffee Lover >= 5.0 -> Pausa para Café às 15:30 (45 min)
        if profile.get_intensity("Coffee Lover") >= 5.0:
            top_cafes = self.dining_service.recommend_meal_places(
                reference_location, cafe_candidates, limit=3
            )
            slots.append(
                MealSlot(
                    id="slot-coffee",
                    name="Pausa para Café",
                    window=TimeWindow(start_time=time(15, 30), end_time=time(16, 15)),
                    recommended_places=top_cafes,
                    selected_place=top_cafes[0] if top_cafes else None,
                    estimated_cost=35.0,
                )
            )

        # Wine Lover >= 5.0 -> Degustação / Wine Bar às 18:00 (1h15)
        if profile.get_intensity("Wine Lover") >= 5.0:
            top_wine_bars = self.dining_service.recommend_meal_places(
                reference_location, wine_candidates, limit=3
            )
            slots.append(
                MealSlot(
                    id="slot-wine",
                    name="Degustação / Wine Bar",
                    window=TimeWindow(start_time=time(18, 0), end_time=time(19, 15)),
                    recommended_places=top_wine_bars,
                    selected_place=top_wine_bars[0] if top_wine_bars else None,
                    estimated_cost=120.0,
                )
            )

        return slots
