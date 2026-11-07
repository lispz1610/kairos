from datetime import date

from src.core.domain.models import (
    POI,
    Accommodation,
    Coordinates,
    Trip,
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
