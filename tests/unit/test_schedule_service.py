from datetime import date

from src.core.domain.models import Accommodation, Coordinates, InterCityConnection, Trip, TripStage
from src.core.services.schedule import ScheduleService


def test_ripple_shift_extends_stage_and_shifts_subsequent_stages_and_connections() -> None:
    hotel_sp = Accommodation(
        id="h-sp", name="Hotel SP", location=Coordinates(latitude=-23.5, longitude=-46.6)
    )
    hotel_lima = Accommodation(
        id="h-lima", name="Hotel Lima", location=Coordinates(latitude=-12.0, longitude=-77.0)
    )

    stage_sp = TripStage.create(
        id="stage-sp",
        city_name="São Paulo",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 10),  # 9 days
        base_accommodation=hotel_sp,
    )
    stage_lima = TripStage.create(
        id="stage-lima",
        city_name="Lima",
        start_date=date(2026, 11, 10),
        end_date=date(2026, 11, 15),  # 5 days
        base_accommodation=hotel_lima,
    )
    flight = InterCityConnection(
        id="flight-1",
        from_stage_id="stage-sp",
        to_stage_id="stage-lima",
        departure_time=date(2026, 11, 10),
    )

    trip = Trip(
        id="trip-1",
        title="SP e Lima",
        stages=[stage_sp, stage_lima],
        connections=[flight],
    )

    service = ScheduleService()
    # User extends São Paulo by +1 day (from 1-10 to 1-11)
    preview = service.preview_ripple_shift(trip, target_stage_id="stage-sp", delta_days=1)
    assert preview.delta_days == 1
    assert preview.new_target_end == date(2026, 11, 11)

    updated_trip = service.apply_ripple_shift(trip, target_stage_id="stage-sp", delta_days=1)

    # São Paulo now has 10 days (1 to 11)
    assert len(updated_trip.stages[0].days) == 10
    assert updated_trip.stages[0].end_date == date(2026, 11, 11)
    assert updated_trip.stages[0].days[-1].date == date(2026, 11, 10)

    # Lima shifted to 11 to 16, preserving exactly its 5 days
    assert updated_trip.stages[1].start_date == date(2026, 11, 11)
    assert updated_trip.stages[1].end_date == date(2026, 11, 16)
    assert len(updated_trip.stages[1].days) == 5
    assert updated_trip.stages[1].days[0].date == date(2026, 11, 11)
    assert updated_trip.stages[1].days[-1].date == date(2026, 11, 15)

    # Flight connection departure shifted to Nov 11
    assert updated_trip.connections[0].departure_time == date(2026, 11, 11)
