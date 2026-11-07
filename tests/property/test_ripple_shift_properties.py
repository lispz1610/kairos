from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from src.core.domain.models import Accommodation, Coordinates, Trip, TripStage
from src.core.services.schedule import ScheduleService


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
    trip = Trip(id="trip", title="Test Trip", stages=[st1, st2])

    service = ScheduleService()
    # Guard: do not reduce stage to < 1 day
    if days_stage_1 + delta_days < 1:
        return

    updated_trip = service.apply_ripple_shift(trip, target_stage_id="st1", delta_days=delta_days)

    # Invariant 1: Stage 1 duration updated
    assert len(updated_trip.stages[0].days) == days_stage_1 + delta_days
    # Invariant 2: Stage 2 duration strictly preserved
    assert len(updated_trip.stages[1].days) == days_stage_2
    # Invariant 3: Stage 2 start aligns with Stage 1 end
    assert updated_trip.stages[1].start_date == updated_trip.stages[0].end_date
    # Invariant 4: No overlapping dates
    assert updated_trip.stages[0].end_date <= updated_trip.stages[1].start_date
