from __future__ import annotations

from datetime import time
from typing import Dict, List

from pydantic import BaseModel

from src.core.domain.models import POI, Coordinates, MealSlot, TimeWindow, Trip
from src.core.solvers.optw import haversine_distance_km

PRICE_TIER_ESTIMATES: Dict[str, float] = {
    "$": 45.0,
    "$$": 95.0,
    "$$$": 190.0,
    "$$$$": 380.0,
}

HOTEL_TIER_DEFAULTS: Dict[str, float] = {
    "$": 200.0,
    "$$": 450.0,
    "$$$": 750.0,
    "$$$$": 1000.0,
}

DAILY_FOOD_PROFILES: Dict[str, float] = {
    "budget": 80.0,
    "moderate": 180.0,
    "fine_dining": 400.0,
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
        if not candidates:
            return []

        def score_candidate(poi: POI) -> float:
            distance = haversine_distance_km(reference_location, poi.location)
            proximity_score = 1.0 / max(0.1, distance)
            award_bonus = 2.0 if poi.awards else 0.0
            rating_bonus = (poi.rating or 4.0) * 0.5
            return proximity_score + award_bonus + rating_bonus

        sorted_candidates = sorted(candidates, key=score_candidate, reverse=True)
        return sorted_candidates[:limit]

    def create_default_meal_slots(
        self,
        reference_location: Coordinates,
        restaurant_candidates: List[POI],
    ) -> List[MealSlot]:
        lunch_picks = self.recommend_meal_places(
            reference_location, restaurant_candidates, limit=3
        )
        dinner_picks = self.recommend_meal_places(
            reference_location, restaurant_candidates, limit=3
        )

        lunch_slot = MealSlot(
            id="slot-lunch",
            name="Almoço",
            window=TimeWindow(start_time=time(12, 30), end_time=time(14, 0)),
            recommended_places=lunch_picks,
            selected_place=lunch_picks[0] if lunch_picks else None,
            estimated_cost=PRICE_TIER_ESTIMATES.get(
                lunch_picks[0].price_tier or "$$", 95.0
            ) if lunch_picks else 95.0,
        )

        dinner_slot = MealSlot(
            id="slot-dinner",
            name="Jantar",
            window=TimeWindow(start_time=time(19, 30), end_time=time(21, 0)),
            recommended_places=dinner_picks,
            selected_place=dinner_picks[0] if dinner_picks else None,
            estimated_cost=PRICE_TIER_ESTIMATES.get(
                dinner_picks[0].price_tier or "$$$", 190.0
            ) if dinner_picks else 190.0,
        )

        return [lunch_slot, dinner_slot]

    def calculate_trip_budget(
        self, trip: Trip, food_profile: str = "moderate"
    ) -> BudgetSummary:
        daily_food_rate = DAILY_FOOD_PROFILES.get(food_profile.lower(), 180.0)

        total_accommodation = 0.0
        total_dining = 0.0
        breakdowns: Dict[str, StageBudgetBreakdown] = {}

        for stage in trip.stages:
            stage_acc_cost = 0.0
            stage_dining_cost = 0.0
            stage_days = len(stage.days)

            for day in stage.days:
                hotel = day.custom_accommodation or stage.base_accommodation
                rate = (
                    hotel.real_daily_rate
                    if hotel.real_daily_rate is not None
                    else (
                        day.effective_accommodation.real_daily_rate
                        if day.effective_accommodation.real_daily_rate is not None
                        else HOTEL_TIER_DEFAULTS.get(hotel.price_tier, 450.0)
                    )
                )
                stage_acc_cost += rate

                # Soma o custo das refeições selecionadas no dia ou usa perfil
                day_dining = sum(
                    slot.estimated_cost
                    for slot in day.meal_slots
                    if slot.estimated_cost is not None
                )
                stage_dining_cost += day_dining if day_dining > 0 else daily_food_rate

            total_accommodation += stage_acc_cost
            total_dining += stage_dining_cost

            breakdowns[stage.id] = StageBudgetBreakdown(
                accommodation_cost=stage_acc_cost,
                dining_cost=stage_dining_cost,
                total_cost=stage_acc_cost + stage_dining_cost,
                days_count=stage_days,
            )

        return BudgetSummary(
            total_accommodation_cost=total_accommodation,
            total_dining_cost=total_dining,
            total_trip_cost=total_accommodation + total_dining,
            stage_breakdowns=breakdowns,
        )
