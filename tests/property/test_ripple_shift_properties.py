import json
from datetime import date, time, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from src.core.domain.models import (
    POI,
    Accommodation,
    Coordinates,
    InterCityConnection,
    Itinerary,
    ItineraryStop,
    TransportMode,
    Trip,
    TripStage,
)
from src.core.services.schedule import ScheduleService


@settings(deadline=None)
@given(
    days_stage_1=st.integers(min_value=3, max_value=10),
    days_stage_2=st.integers(min_value=2, max_value=8),
    delta_days=st.integers(min_value=-2, max_value=4),
)
def test_ripple_shift_invariants(
    days_stage_1: int,
    days_stage_2: int,
    delta_days: int,
) -> None:
    """Invariante: o Deslocamento em Cascata preserva a duração das Etapas seguintes."""
    hotel = Accommodation(
        id="h", name="Hotel", location=Coordinates(latitude=0.0, longitude=0.0)
    )
    start_d1 = date(2026, 6, 1)
    end_d1 = start_d1 + timedelta(days=days_stage_1)

    start_d2 = end_d1
    end_d2 = start_d2 + timedelta(days=days_stage_2)

    st1 = TripStage.create(
        id="st1",
        city_name="City 1",
        start_date=start_d1,
        end_date=end_d1,
        base_accommodation=hotel,
    )
    st2 = TripStage.create(
        id="st2",
        city_name="City 2",
        start_date=start_d2,
        end_date=end_d2,
        base_accommodation=hotel,
    )

    # Populate future stage with itinerary stops / POIs
    for day_idx, day in enumerate(st2.days):
        poi_morning = POI(
            id=f"poi_st2_d{day_idx}_morning",
            name=f"Atração Manhã Dia {day_idx}",
            location=Coordinates(latitude=-23.55 + day_idx * 0.01, longitude=-46.63),
            stay_duration_minutes=90,
            utility_score=7.5 + (day_idx % 3),
        )
        poi_afternoon = POI(
            id=f"poi_st2_d{day_idx}_afternoon",
            name=f"Atração Tarde Dia {day_idx}",
            location=Coordinates(latitude=-23.56 + day_idx * 0.01, longitude=-46.64),
            stay_duration_minutes=120,
            utility_score=8.0,
        )
        day.itinerary = Itinerary(
            stops=[
                ItineraryStop(
                    poi=poi_morning,
                    arrival_time=time(10, 0),
                    departure_time=time(11, 30),
                    transit_duration_minutes=15,
                ),
                ItineraryStop(
                    poi=poi_afternoon,
                    arrival_time=time(14, 0),
                    departure_time=time(16, 0),
                    transit_duration_minutes=20,
                ),
            ],
            total_utility=15.5 + (day_idx % 3),
            total_duration_minutes=245,
        )

    conn = InterCityConnection(
        id="conn-st1-st2",
        from_stage_id="st1",
        to_stage_id="st2",
        mode=TransportMode.FLYING,
        departure_time=end_d1,
    )

    trip = Trip(id="trip", title="Test Trip", stages=[st1, st2], connections=[conn])

    service = ScheduleService()
    # Guard: do not reduce stage to < 1 day
    if days_stage_1 + delta_days < 1:
        return

    # Record pre-shift POI sequence and connection departure
    initial_conn_date = trip.connections[0].departure_time
    initial_poi_ids = [
        stop.poi.id
        for day in trip.stages[1].days
        if day.itinerary
        for stop in day.itinerary.stops
    ]

    updated_trip = service.apply_ripple_shift(trip, target_stage_id="st1", delta_days=delta_days)

    # Invariant 1: Stage 1 duration updated
    assert len(updated_trip.stages[0].days) == days_stage_1 + delta_days
    # Invariant 2: Stage 2 duration strictly preserved
    assert len(updated_trip.stages[1].days) == days_stage_2
    # Invariant 3: Stage 2 start aligns with Stage 1 end
    assert updated_trip.stages[1].start_date == updated_trip.stages[0].end_date
    # Invariant 4: No overlapping dates
    assert updated_trip.stages[0].end_date <= updated_trip.stages[1].start_date

    # Invariant 5: InterCityConnection departure date is shifted proportionally
    expected_conn_date = initial_conn_date + timedelta(days=delta_days)
    assert updated_trip.connections[0].departure_time == expected_conn_date
    assert updated_trip.connections[0].departure_time == updated_trip.stages[1].start_date

    # Invariant 6: Sequence of future POIs is never corrupted
    after_poi_ids = [
        stop.poi.id
        for day in updated_trip.stages[1].days
        if day.itinerary
        for stop in day.itinerary.stops
    ]
    assert after_poi_ids == initial_poi_ids

    # Invariant 7: Per-day stops inside future stage retain exact attributes
    for day_idx, day in enumerate(updated_trip.stages[1].days):
        assert day.itinerary is not None
        assert len(day.itinerary.stops) == 2
        assert day.itinerary.stops[0].poi.id == f"poi_st2_d{day_idx}_morning"
        assert day.itinerary.stops[1].poi.id == f"poi_st2_d{day_idx}_afternoon"
        assert day.itinerary.stops[0].arrival_time == time(10, 0)
        assert day.itinerary.stops[1].arrival_time == time(14, 0)


@st.composite
def arbitrary_trips(draw: st.DrawFn) -> Trip:
    """Gera Viagens com Etapas e Conexões Interurbanas arbitrárias."""
    num_stages = draw(st.integers(min_value=1, max_value=3))
    stages = []
    connections = []
    base_date = date(2026, 9, 1)
    current_date = base_date

    for i in range(num_stages):
        stage_id = f"st_{i}"
        duration = draw(st.integers(min_value=1, max_value=4))
        end_date = current_date + timedelta(days=duration)
        lat = round(draw(st.floats(min_value=-80.0, max_value=80.0)), 4)
        lon = round(draw(st.floats(min_value=-170.0, max_value=170.0)), 4)
        rate = round(draw(st.floats(min_value=100.0, max_value=1500.0)), 2)
        tier = draw(st.sampled_from(["$", "$$", "$$$", "$$$$"]))

        base_hotel = Accommodation(
            id=f"base_hotel_{i}",
            name=f"Hotel Base {i}",
            location=Coordinates(latitude=lat, longitude=lon),
            price_tier=tier,
            real_daily_rate=rate,
        )
        stage = TripStage.create(
            id=stage_id,
            city_name=f"Cidade {i}",
            start_date=current_date,
            end_date=end_date,
            base_accommodation=base_hotel,
        )

        # Optionally override accommodation on a day
        if duration > 1 and draw(st.booleans()):
            override_day = draw(st.integers(min_value=1, max_value=duration - 1))
            custom_hotel = Accommodation(
                id=f"custom_hotel_{i}_{override_day}",
                name=f"Custom Hotel {i}-{override_day}",
                location=Coordinates(latitude=lat + 0.01, longitude=lon + 0.01),
                price_tier="$$$$",
                real_daily_rate=999.0,
            )
            stage.override_accommodation(override_day, custom_hotel)
            stage.days[override_day].include_luggage_dropoff = draw(st.booleans())

        stages.append(stage)

        if i > 0:
            mode = draw(st.sampled_from(list(TransportMode)))
            connections.append(
                InterCityConnection(
                    id=f"conn_{i-1}_{i}",
                    from_stage_id=f"st_{i-1}",
                    to_stage_id=stage_id,
                    mode=mode,
                    departure_time=current_date,
                )
            )

        current_date = end_date

    travelers = draw(st.integers(min_value=1, max_value=6))
    return Trip(
        id=f"trip-{draw(st.integers(min_value=1, max_value=9999))}",
        title="Viagem Arbitrária",
        travelers=travelers,
        stages=stages,
        connections=connections,
    )


@settings(deadline=None)
@given(trip=arbitrary_trips())
def test_trip_json_round_trip_idempotence(trip: Trip) -> None:
    # Validate round-trip via json.loads(trip.model_dump_json())
    """Invariante: serializar e desserializar a Viagem preserva dados e dias de transição."""
    dumped_json_str = trip.model_dump_json()
    dict_payload = json.loads(dumped_json_str)
    restored = Trip.model_validate(dict_payload)

    # Idempotence: Trip.model_validate(json.loads(trip.model_dump_json())) == trip
    assert restored == trip
    assert Trip.model_validate_json(dumped_json_str) == trip

    # Invariant: transition day calculation remains consistent after round-trip
    for orig_stage, restored_stage in zip(trip.stages, restored.stages):
        for orig_day, restored_day in zip(orig_stage.days, restored_stage.days):
            assert restored_day.is_transition_day == orig_day.is_transition_day
            assert (
                restored_day.effective_accommodation.id
                == orig_day.effective_accommodation.id
            )
