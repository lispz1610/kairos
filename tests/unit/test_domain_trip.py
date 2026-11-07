from datetime import date

from src.core.domain.models import (
    Accommodation,
    Coordinates,
    InterCityConnection,
    TransportMode,
    Trip,
    TripStage,
)


def test_accommodation_creation_and_coordinates() -> None:
    hotel = Accommodation(
        id="hotel-sp-1",
        name="Hotel Fasano São Paulo",
        location=Coordinates(latitude=-23.5629, longitude=-46.6682),
        price_tier="$$$$",
        real_daily_rate=1200.0,
    )
    assert hotel.id == "hotel-sp-1"
    assert hotel.location.latitude == -23.5629
    assert hotel.real_daily_rate == 1200.0


def test_trip_stage_days_generation_with_base_hotel() -> None:
    base_hotel = Accommodation(
        id="hotel-sp-base",
        name="Hotel Ibis Paulista",
        location=Coordinates(latitude=-23.555, longitude=-46.660),
        price_tier="$$",
        real_daily_rate=350.0,
    )
    stage = TripStage.create(
        id="stage-sp",
        city_name="São Paulo",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 4),  # 3 days: Nov 1, Nov 2, Nov 3
        base_accommodation=base_hotel,
    )

    assert len(stage.days) == 3
    assert stage.days[0].date == date(2026, 11, 1)
    assert stage.days[1].date == date(2026, 11, 2)
    assert stage.days[2].date == date(2026, 11, 3)

    # All days inherit the base hotel
    for day in stage.days:
        assert day.effective_accommodation.id == "hotel-sp-base"
        assert not day.is_transition_day


def test_trip_stage_custom_hotel_override_and_transition_detection() -> None:
    base_hotel = Accommodation(
        id="hotel-base",
        name="Hotel Base",
        location=Coordinates(latitude=-23.55, longitude=-46.66),
    )
    boutique_hotel = Accommodation(
        id="hotel-boutique",
        name="Hotel Boutique",
        location=Coordinates(latitude=-23.57, longitude=-46.68),
    )
    stage = TripStage.create(
        id="stage-sp",
        city_name="São Paulo",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 4),
        base_accommodation=base_hotel,
    )

    # Override day 3
    stage.override_accommodation(day_index=2, accommodation=boutique_hotel)

    assert stage.days[0].effective_accommodation.id == "hotel-base"
    assert not stage.days[0].is_transition_day

    assert stage.days[1].effective_accommodation.id == "hotel-base"
    assert not stage.days[1].is_transition_day

    # Day 3 has changed hotel: woke up at Hotel Base, sleeps at Hotel Boutique
    assert stage.days[2].effective_accommodation.id == "hotel-boutique"
    assert stage.days[2].is_transition_day
    assert stage.days[2].departure_accommodation.id == "hotel-base"
    assert stage.days[2].return_accommodation.id == "hotel-boutique"


def test_trip_full_json_serialization_round_trip() -> None:
    base_hotel_sp = Accommodation(
        id="hotel-sp",
        name="Hotel SP",
        location=Coordinates(latitude=-23.55, longitude=-46.66),
    )
    stage_sp = TripStage.create(
        id="stage-sp",
        city_name="São Paulo",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 4),
        base_accommodation=base_hotel_sp,
    )

    base_hotel_lima = Accommodation(
        id="hotel-lima",
        name="Hotel Lima",
        location=Coordinates(latitude=-12.04, longitude=-77.03),
    )
    stage_lima = TripStage.create(
        id="stage-lima",
        city_name="Lima",
        start_date=date(2026, 11, 4),
        end_date=date(2026, 11, 8),
        base_accommodation=base_hotel_lima,
    )

    flight = InterCityConnection(
        id="conn-sp-lima",
        from_stage_id="stage-sp",
        to_stage_id="stage-lima",
        mode=TransportMode.FLYING,
        departure_time=date(2026, 11, 4),
    )

    trip = Trip(
        id="trip-1",
        title="Viagem São Paulo e Lima",
        stages=[stage_sp, stage_lima],
        connections=[flight],
    )

    json_data = trip.model_dump_json()
    restored_trip = Trip.model_validate_json(json_data)

    assert restored_trip.id == trip.id
    assert len(restored_trip.stages) == 2
    assert restored_trip.stages[0].days[0].effective_accommodation.name == "Hotel SP"
    assert restored_trip.stages[1].days[0].effective_accommodation.name == "Hotel Lima"
