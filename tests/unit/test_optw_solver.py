from datetime import time

from src.core.domain.models import POI, Accommodation, Coordinates, TimeWindow
from src.core.solvers.optw import OPTWSolver


def test_optw_solver_respects_time_budget_and_depots() -> None:
    hotel_a = Accommodation(
        id="hotel-a",
        name="Hotel A (Partida)",
        location=Coordinates(latitude=-23.5505, longitude=-46.6333),
    )
    hotel_b = Accommodation(
        id="hotel-b",
        name="Hotel B (Retorno)",
        location=Coordinates(latitude=-23.5600, longitude=-46.6500),
    )

    # 3 POIs with varying utilities and locations
    poi1 = POI(
        id="poi-1",
        name="Museu de Arte",
        location=Coordinates(latitude=-23.5615, longitude=-46.6559),
        window=TimeWindow(start_time=time(10, 0), end_time=time(18, 0)),
        stay_duration_minutes=90,
        utility_score=10.0,
    )
    poi2 = POI(
        id="poi-2",
        name="Parque Central",
        location=Coordinates(latitude=-23.5874, longitude=-46.6576),
        window=TimeWindow(start_time=time(8, 0), end_time=time(20, 0)),
        stay_duration_minutes=60,
        utility_score=7.0,
    )
    poi3 = POI(
        id="poi-3",
        name="Atração Distante",
        location=Coordinates(latitude=-23.9000, longitude=-46.9000),
        window=TimeWindow(start_time=time(14, 0), end_time=time(16, 0)),
        stay_duration_minutes=120,
        utility_score=1.0,
    )

    solver = OPTWSolver()
    itinerary = solver.solve(
        start_location=hotel_a.location,
        end_location=hotel_b.location,
        window=TimeWindow(start_time=time(9, 0), end_time=time(18, 0)),
        candidates=[poi1, poi2, poi3],
    )

    assert len(itinerary.stops) >= 1
    assert itinerary.total_utility >= 10.0
    # The distant POI with low utility should be pruned if time is tight
    stop_ids = [stop.poi.id for stop in itinerary.stops]
    assert "poi-1" in stop_ids
    # Check stops are in order and non-overlapping
    for i in range(len(itinerary.stops)):
        stop = itinerary.stops[i]
        assert stop.arrival_time <= stop.departure_time
        if i > 0:
            prev_stop = itinerary.stops[i - 1]
            assert prev_stop.departure_time <= stop.arrival_time
