from __future__ import annotations

from datetime import time
from typing import Dict, List, Optional

from pydantic import BaseModel

from src.core.domain.models import (
    POI,
    Accommodation,
    Coordinates,
    FoodProfile,
    Itinerary,
    MealSlot,
    PreferencesProfile,
    PriceTier,
    TimeWindow,
    Trip,
    TripDay,
)
from src.core.solvers.optw import haversine_distance_km

PRICE_TIER_ESTIMATES: Dict[str, float] = {
    PriceTier.BUDGET: 45.0,
    PriceTier.MODERATE: 95.0,
    PriceTier.COMFORT: 190.0,
    PriceTier.LUXURY: 380.0,
}

ACCOMMODATION_TIER_DEFAULTS: Dict[str, float] = {
    PriceTier.BUDGET: 200.0,
    PriceTier.MODERATE: 300.0,
    PriceTier.COMFORT: 450.0,
    PriceTier.LUXURY: 1000.0,
}
HOTEL_TIER_DEFAULTS = ACCOMMODATION_TIER_DEFAULTS

DAILY_FOOD_PROFILES: Dict[str, float] = {
    FoodProfile.BUDGET: 80.0,
    FoodProfile.MODERATE: 180.0,
    FoodProfile.FINE_DINING: 400.0,
}


class StageBudgetBreakdown(BaseModel):
    accommodation_cost: float
    dining_cost: float
    total_cost: float
    days_count: int


class BudgetSummary(BaseModel):
    total_accommodation_cost: float
    total_dining_cost: float
    total_trip_cost: float
    stage_breakdowns: Dict[str, StageBudgetBreakdown]


class DiningService:
    """Serviço de recomendação contextual de gastronomia e projeção orçamentária."""

    def recommend_meal_places(
        self,
        reference_location: Coordinates,
        candidates: List[POI],
        limit: int = 3,
    ) -> List[POI]:
        """Classifica e recomenda os melhores estabelecimentos por proximidade e premiações."""
        if not candidates:
            return []

        def score_candidate(poi: POI) -> float:
            distance = haversine_distance_km(reference_location, poi.location)
            proximity_score = 1.0 / max(0.1, distance)
            award_bonus = 2.0 if poi.awards else 0.0
            rating_bonus = (poi.rating or 4.0) * 0.5
            utility_bonus = (poi.utility_score or 1.0) * 0.2
            return proximity_score + award_bonus + rating_bonus + utility_bonus

        sorted_candidates = sorted(candidates, key=score_candidate, reverse=True)
        return sorted_candidates[:limit]

    def get_contextual_location_for_slot(
        self,
        slot_window: TimeWindow,
        departure_location: Coordinates,
        return_location: Coordinates,
        itinerary: Optional[Itinerary],
        fallback_to_return: bool = False,
    ) -> Coordinates:
        """Determina a coordenada de referência para o slot com base no último POI anterior."""
        if itinerary and itinerary.stops:
            slot_start = slot_window.start_time
            prior_stops = [
                s for s in itinerary.stops if s.departure_time <= slot_start
            ]
            if prior_stops:
                return prior_stops[-1].poi.location
        return return_location if fallback_to_return else departure_location

    def _build_meal_slot(
        self,
        slot_id: str,
        name: str,
        window: TimeWindow,
        reference_location: Coordinates,
        candidates: List[POI],
        default_cost: float,
        fallback_tier: PriceTier = PriceTier.MODERATE,
    ) -> MealSlot:
        picks = self.recommend_meal_places(reference_location, candidates, limit=3)
        selected = picks[0] if picks else None
        tier = selected.price_tier if selected and selected.price_tier else fallback_tier
        cost = PRICE_TIER_ESTIMATES.get(tier, default_cost) if selected else default_cost

        return MealSlot(
            id=slot_id,
            name=name,
            window=window,
            recommended_places=picks,
            selected_place=selected,
            estimated_cost=cost,
        )

    def create_contextual_meal_slots(
        self,
        departure_location: Coordinates,
        return_location: Coordinates,
        restaurant_candidates: List[POI],
        itinerary: Optional[Itinerary] = None,
        preferences: Optional[PreferencesProfile] = None,
        cafe_candidates: Optional[List[POI]] = None,
        wine_candidates: Optional[List[POI]] = None,
    ) -> List[MealSlot]:
        """Cria slots de refeição e pausas experienciais com recomendações contextuais Top 3."""
        lunch_win = TimeWindow(start_time=time(12, 30), end_time=time(14, 0))
        dinner_win = TimeWindow(start_time=time(19, 30), end_time=time(21, 0))

        lunch_loc = self.get_contextual_location_for_slot(
            lunch_win, departure_location, return_location, itinerary, fallback_to_return=False
        )
        dinner_loc = self.get_contextual_location_for_slot(
            dinner_win, departure_location, return_location, itinerary, fallback_to_return=True
        )

        slots: List[MealSlot] = [
            self._build_meal_slot(
                "slot-lunch",
                "Almoço",
                lunch_win,
                lunch_loc,
                restaurant_candidates,
                95.0,
                PriceTier.MODERATE,
            ),
            self._build_meal_slot(
                "slot-dinner",
                "Jantar",
                dinner_win,
                dinner_loc,
                restaurant_candidates,
                190.0,
                PriceTier.COMFORT,
            ),
        ]

        if preferences:
            self._append_thematic_slots(
                slots=slots,
                departure_location=departure_location,
                return_location=return_location,
                itinerary=itinerary,
                preferences=preferences,
                restaurant_candidates=restaurant_candidates,
                cafe_candidates=cafe_candidates,
                wine_candidates=wine_candidates,
            )

        return sorted(slots, key=lambda s: s.window.start_time)

    def _append_coffee_slot(
        self,
        slots: List[MealSlot],
        departure_location: Coordinates,
        return_location: Coordinates,
        itinerary: Optional[Itinerary],
        preferences: PreferencesProfile,
        candidates: List[POI],
        cafe_candidates: Optional[List[POI]],
    ) -> None:
        if preferences.get_intensity("Coffee Lover") < 5.0:
            return
        c_win = TimeWindow(start_time=time(15, 30), end_time=time(16, 15))
        c_loc = self.get_contextual_location_for_slot(
            c_win, departure_location, return_location, itinerary, fallback_to_return=False
        )
        pool = cafe_candidates or [
            p for p in candidates if "cafe" in p.category.lower() or "coffee" in p.category.lower()
        ]
        cafes = pool if pool else candidates
        slots.append(
            self._build_meal_slot(
                "slot-coffee", "Pausa para Café", c_win, c_loc, cafes, 35.0, PriceTier.BUDGET
            )
        )

    def _append_wine_slot(
        self,
        slots: List[MealSlot],
        departure_location: Coordinates,
        return_location: Coordinates,
        itinerary: Optional[Itinerary],
        preferences: PreferencesProfile,
        candidates: List[POI],
        wine_candidates: Optional[List[POI]],
    ) -> None:
        if preferences.get_intensity("Wine Lover") < 5.0:
            return
        w_win = TimeWindow(start_time=time(18, 0), end_time=time(19, 15))
        w_loc = self.get_contextual_location_for_slot(
            w_win, departure_location, return_location, itinerary, fallback_to_return=True
        )
        pool = wine_candidates or [
            p for p in candidates if "wine" in p.category.lower() or "bar" in p.category.lower()
        ]
        wines = pool if pool else candidates
        slots.append(
            self._build_meal_slot(
                "slot-wine", "Degustação / Wine Bar", w_win, w_loc, wines, 120.0, PriceTier.COMFORT
            )
        )

    def _append_thematic_slots(
        self,
        slots: List[MealSlot],
        departure_location: Coordinates,
        return_location: Coordinates,
        itinerary: Optional[Itinerary],
        preferences: PreferencesProfile,
        restaurant_candidates: List[POI],
        cafe_candidates: Optional[List[POI]],
        wine_candidates: Optional[List[POI]],
    ) -> None:
        self._append_coffee_slot(
            slots,
            departure_location,
            return_location,
            itinerary,
            preferences,
            restaurant_candidates,
            cafe_candidates,
        )
        self._append_wine_slot(
            slots,
            departure_location,
            return_location,
            itinerary,
            preferences,
            restaurant_candidates,
            wine_candidates,
        )

    def create_default_meal_slots(
        self,
        reference_location: Coordinates,
        restaurant_candidates: List[POI],
    ) -> List[MealSlot]:
        """Cria slots de refeição padrão (almoço e jantar) para uma coordenada de referência."""
        return self.create_contextual_meal_slots(
            departure_location=reference_location,
            return_location=reference_location,
            restaurant_candidates=restaurant_candidates,
        )

    def _get_day_accommodation_rate(
        self, day: TripDay, base_accommodation: Accommodation
    ) -> float:
        accommodation = day.custom_accommodation or base_accommodation
        if accommodation.real_daily_rate is not None:
            return accommodation.real_daily_rate
        if day.effective_accommodation.real_daily_rate is not None:
            return day.effective_accommodation.real_daily_rate
        return ACCOMMODATION_TIER_DEFAULTS.get(accommodation.price_tier, 450.0)

    def _get_day_dining_cost(
        self, day: TripDay, daily_food_rate: float, num_travelers: int = 1
    ) -> float:
        day_dining = sum(
            slot.estimated_cost
            for slot in day.meal_slots
            if slot.estimated_cost is not None
        )
        base_cost = day_dining if day_dining > 0 else daily_food_rate
        return base_cost * num_travelers

    def calculate_trip_budget(
        self, trip: Trip, food_profile: FoodProfile | str = FoodProfile.MODERATE
    ) -> BudgetSummary:
        """Consolida os custos estimados de hospedagem e alimentação por etapa e globais."""
        profile_key = getattr(food_profile, "value", str(food_profile)).lower()
        daily_food_rate = DAILY_FOOD_PROFILES.get(profile_key, 180.0)
        num_travelers = max(1, getattr(trip, "travelers", 1) or 1)

        total_accommodation = 0.0
        total_dining = 0.0
        breakdowns: Dict[str, StageBudgetBreakdown] = {}

        for stage in trip.stages:
            stage_acc_cost = 0.0
            stage_dining_cost = 0.0

            for day in stage.days:
                stage_acc_cost += self._get_day_accommodation_rate(
                    day, stage.base_accommodation
                )
                stage_dining_cost += self._get_day_dining_cost(
                    day, daily_food_rate, num_travelers
                )

            total_accommodation += stage_acc_cost
            total_dining += stage_dining_cost

            breakdowns[stage.id] = StageBudgetBreakdown(
                accommodation_cost=stage_acc_cost,
                dining_cost=stage_dining_cost,
                total_cost=stage_acc_cost + stage_dining_cost,
                days_count=len(stage.days),
            )

        return BudgetSummary(
            total_accommodation_cost=total_accommodation,
            total_dining_cost=total_dining,
            total_trip_cost=total_accommodation + total_dining,
            stage_breakdowns=breakdowns,
        )
