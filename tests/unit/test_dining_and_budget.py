from datetime import date, time

import pytest

from src.core.domain.models import (
    POI,
    Accommodation,
    Coordinates,
    FoodProfile,
    MealSlot,
    TimeWindow,
    Trip,
    TripDay,
    TripStage,
)
from src.core.services.dining_and_budget import DiningService


def test_dining_service_proximity_recommendations() -> None:
    # Reference POI (e.g. visited at morning)
    masp_location = Coordinates(latitude=-23.5615, longitude=-46.6559)

    # 3 restaurant candidates at different distances
    r_close_michelin = POI(
        id="rest-1",
        name="A Baianeira MASP",
        location=Coordinates(latitude=-23.5616, longitude=-46.6560),  # next door
        category="restaurant",
        rating=4.7,
        price_tier="$$",
        awards=["Bib Gourmand Michelin"],
        utility_score=9.5,
    )
    r_medium = POI(
        id="rest-2",
        name="Restaurante Jardins",
        location=Coordinates(latitude=-23.5680, longitude=-46.6650),  # ~1.2 km
        category="restaurant",
        rating=4.5,
        price_tier="$$$",
        utility_score=8.0,
    )
    r_far = POI(
        id="rest-3",
        name="Churrascaria Distante",
        location=Coordinates(latitude=-23.6500, longitude=-46.7200),  # > 10 km
        category="restaurant",
        rating=4.8,
        price_tier="$$$$",
        utility_score=9.0,
    )

    service = DiningService()
    top_picks = service.recommend_meal_places(
        reference_location=masp_location,
        candidates=[r_far, r_medium, r_close_michelin],
        limit=2,
    )

    assert len(top_picks) == 2
    # Nearest high-rated restaurant should be first
    assert top_picks[0].id == "rest-1"
    assert top_picks[1].id == "rest-2"


def test_budget_calculation_consolidates_lodging_and_food() -> None:
    hotel_sp = Accommodation(
        id="h-sp",
        name="Hotel SP",
        location=Coordinates(latitude=-23.55, longitude=-46.66),
        real_daily_rate=400.0,
    )
    stage_sp = TripStage.create(
        id="stage-sp",
        city_name="São Paulo",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 4),  # 3 days
        base_accommodation=hotel_sp,
    )
    trip = Trip(id="trip-1", title="Viagem SP", stages=[stage_sp])

    service = DiningService()
    budget = service.calculate_trip_budget(trip, food_profile="moderate")

    # 3 nights at 400.0 = 1200.0
    assert budget.total_accommodation_cost == 1200.0
    # Moderate food = 180.0/day * 3 days = 540.0
    assert budget.total_dining_cost == 540.0
    # Total = 1740.0
    assert budget.total_trip_cost == 1740.0
    assert "stage-sp" in budget.stage_breakdowns


@pytest.mark.parametrize(
    ("profile", "expected_daily_food"),
    [
        (FoodProfile.BUDGET, 80.0),
        ("budget", 80.0),
        (FoodProfile.MODERATE, 180.0),
        ("moderate", 180.0),
        (FoodProfile.FINE_DINING, 400.0),
        ("fine_dining", 400.0),
    ],
)
def test_budget_calculation_varies_by_food_profile(
    profile: FoodProfile | str, expected_daily_food: float
) -> None:
    hotel = Accommodation(
        id="h-sp",
        name="Hotel SP",
        location=Coordinates(latitude=-23.55, longitude=-46.66),
        real_daily_rate=300.0,
    )
    stage = TripStage.create(
        id="st-sp",
        city_name="São Paulo",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 4),  # 3 days
        base_accommodation=hotel,
    )
    trip = Trip(id="trip-test", title="Trip Test", stages=[stage], travelers=1)

    service = DiningService()
    budget = service.calculate_trip_budget(trip, food_profile=profile)

    assert budget.total_accommodation_cost == 300.0 * 3
    assert budget.total_dining_cost == expected_daily_food * 3
    assert budget.total_trip_cost == (300.0 * 3) + (expected_daily_food * 3)


@pytest.mark.parametrize("travelers", [1, 2, 4])
def test_budget_calculation_varies_by_travelers_count(travelers: int) -> None:
    hotel = Accommodation(
        id="h-sp",
        name="Hotel SP",
        location=Coordinates(latitude=-23.55, longitude=-46.66),
        real_daily_rate=350.0,
    )
    stage = TripStage.create(
        id="st-sp",
        city_name="São Paulo",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 3),  # 2 days
        base_accommodation=hotel,
    )
    trip = Trip(id="trip-travelers", title="Trip", stages=[stage], travelers=travelers)

    service = DiningService()
    budget = service.calculate_trip_budget(trip, food_profile="moderate")

    # Lodging stays per-room: 2 days * 350.0 = 700.0
    assert budget.total_accommodation_cost == 700.0
    # Moderate food = 180.0/day * 2 days * travelers
    expected_food = 180.0 * 2 * travelers
    assert budget.total_dining_cost == expected_food
    assert budget.total_trip_cost == 700.0 + expected_food


@pytest.mark.parametrize("travelers", [1, 2, 4])
def test_budget_calculation_scales_meal_slots_by_travelers(travelers: int) -> None:
    hotel = Accommodation(
        id="h-sp",
        name="Hotel SP",
        location=Coordinates(latitude=-23.55, longitude=-46.66),
        real_daily_rate=300.0,
    )
    slot_lunch = MealSlot(
        id="slot-lunch",
        name="Almoço",
        window=TimeWindow(start_time=time(12, 30), end_time=time(14, 0)),
        estimated_cost=95.0,
    )
    slot_dinner = MealSlot(
        id="slot-dinner",
        name="Jantar",
        window=TimeWindow(start_time=time(19, 30), end_time=time(21, 0)),
        estimated_cost=190.0,
    )
    day = TripDay(
        date=date(2026, 11, 1),
        base_accommodation=hotel,
        meal_slots=[slot_lunch, slot_dinner],
    )
    stage = TripStage(
        id="st-1",
        city_name="São Paulo",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 2),
        base_accommodation=hotel,
        days=[day],
    )
    trip = Trip(id="t-slots", title="Slots Trip", stages=[stage], travelers=travelers)

    service = DiningService()
    budget = service.calculate_trip_budget(trip, food_profile="moderate")

    # Meal slots total = 95 + 190 = 285.0 per person
    expected_dining = 285.0 * travelers
    assert budget.total_dining_cost == expected_dining
    assert budget.total_accommodation_cost == 300.0
    assert budget.total_trip_cost == 300.0 + expected_dining
