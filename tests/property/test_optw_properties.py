from datetime import time

from hypothesis import given
from hypothesis import strategies as st

from src.core.domain.models import POI, Coordinates, TimeWindow
from src.core.solvers.optw import OPTWSolver


@given(
    lat_start=st.floats(min_value=-23.6, max_value=-23.5),
    lng_start=st.floats(min_value=-46.7, max_value=-46.6),
    lat_end=st.floats(min_value=-23.6, max_value=-23.5),
    lng_end=st.floats(min_value=-46.7, max_value=-46.6),
    num_pois=st.integers(min_value=1, max_value=8),
)
def test_optw_itinerary_never_exceeds_availability_window(
    lat_start: float,
    lng_start: float,
    lat_end: float,
    lng_end: float,
    num_pois: int,
) -> None:
    start_loc = Coordinates(latitude=lat_start, longitude=lng_start)
    end_loc = Coordinates(latitude=lat_end, longitude=lng_end)
    window = TimeWindow(start_time=time(9, 0), end_time=time(18, 0))

    candidates = [
        POI(
            id=f"poi-{i}",
            name=f"Atração {i}",
            location=Coordinates(
                latitude=lat_start + (i * 0.01),
                longitude=lng_start + (i * 0.01),
            ),
            window=TimeWindow(start_time=time(9, 0), end_time=time(18, 0)),
            stay_duration_minutes=45,
            utility_score=float(i + 1),
        )
        for i in range(num_pois)
    ]

    solver = OPTWSolver()
    itinerary = solver.solve(
        start_location=start_loc,
        end_location=end_loc,
        window=window,
        candidates=candidates,
    )

    # Invariant: Total elapsed minutes must never exceed window duration (9h = 540 min)
    assert itinerary.total_duration_minutes <= window.duration_minutes
    for stop in itinerary.stops:
        assert stop.arrival_time >= window.start_time
        assert stop.departure_time <= window.end_time


@given(
    lat_start=st.floats(min_value=-23.6, max_value=-23.5),
    lng_start=st.floats(min_value=-46.7, max_value=-46.6),
    lat_end=st.floats(min_value=-23.6, max_value=-23.5),
    lng_end=st.floats(min_value=-46.7, max_value=-46.6),
    num_pois=st.integers(min_value=1, max_value=8),
    include_coffee=st.booleans(),
    include_wine=st.booleans(),
)
def test_optw_itinerary_never_collides_with_reserved_slots(
    lat_start: float,
    lng_start: float,
    lat_end: float,
    lng_end: float,
    num_pois: int,
    include_coffee: bool,
    include_wine: bool,
) -> None:
    start_loc = Coordinates(latitude=lat_start, longitude=lng_start)
    end_loc = Coordinates(latitude=lat_end, longitude=lng_end)
    window = TimeWindow(start_time=time(9, 0), end_time=time(21, 30))

    reserved_slots = [
        TimeWindow(start_time=time(12, 30), end_time=time(14, 0)),
        TimeWindow(start_time=time(19, 30), end_time=time(21, 0)),
    ]
    if include_coffee:
        reserved_slots.append(TimeWindow(start_time=time(15, 30), end_time=time(16, 15)))
    if include_wine:
        reserved_slots.append(TimeWindow(start_time=time(18, 0), end_time=time(19, 15)))

    candidates = [
        POI(
            id=f"poi-prop-{i}",
            name=f"Atração Prop {i}",
            location=Coordinates(
                latitude=lat_start + (i * 0.005),
                longitude=lng_start + (i * 0.005),
            ),
            window=TimeWindow(start_time=time(9, 0), end_time=time(21, 0)),
            stay_duration_minutes=30 + (i * 15),
            utility_score=float(i + 1),
        )
        for i in range(num_pois)
    ]

    solver = OPTWSolver()
    itinerary = solver.solve(
        start_location=start_loc,
        end_location=end_loc,
        window=window,
        candidates=candidates,
        reserved_slots=reserved_slots,
    )

    # Invariants
    assert itinerary.total_duration_minutes <= window.duration_minutes

    for i, stop in enumerate(itinerary.stops):
        assert stop.arrival_time >= window.start_time
        assert stop.departure_time <= window.end_time
        assert stop.arrival_time <= stop.departure_time

        if i > 0:
            assert itinerary.stops[i - 1].departure_time <= stop.arrival_time

        # Prova formal de ausência absoluta de colisão temporal com slots reservados
        for slot in reserved_slots:
            has_overlap = max(stop.arrival_time, slot.start_time) < min(
                stop.departure_time, slot.end_time
            )
            assert not has_overlap, (
                f"Colisão detectada: parada {stop.poi.id} "
                f"({stop.arrival_time}-{stop.departure_time}) "
                f"sobrepõe slot reservado ({slot.start_time}-{slot.end_time})"
            )
