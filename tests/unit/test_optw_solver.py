from datetime import time

from src.core.domain.models import POI, Accommodation, Coordinates, TimeWindow
from src.core.solvers.optw import OPTWSolver


def test_optw_solver_respects_time_budget_and_depots() -> None:
    """Verifica que o solver respeita orçamento temporal e pontos de partida e retorno."""
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


def test_optw_solver_local_search_2opt_and_swap_optimization() -> None:
    """Verifica que a busca local 2-opt e troca desentrelaça a ordem das paradas."""
    start_loc = Coordinates(latitude=0.0, longitude=0.0)
    end_loc = Coordinates(latitude=0.0, longitude=0.06)

    # Placing POIs in a geometry where greedy insertion order can be optimized by 2-opt/swap
    # Coordinates along a line: A(0.01), B(0.05), C(0.02), D(0.04)
    # If visited 0 -> B -> A -> D -> C -> end, total distance is much higher
    # than 0 -> A -> C -> D -> B -> end
    poi_a = POI(
        id="poi-a",
        name="Parada A",
        location=Coordinates(latitude=0.0, longitude=0.01),
        window=TimeWindow(start_time=time(9, 0), end_time=time(18, 0)),
        stay_duration_minutes=30,
        utility_score=10.0,
    )
    poi_b = POI(
        id="poi-b",
        name="Parada B",
        location=Coordinates(latitude=0.0, longitude=0.05),
        window=TimeWindow(start_time=time(9, 0), end_time=time(18, 0)),
        stay_duration_minutes=30,
        utility_score=10.0,
    )
    poi_c = POI(
        id="poi-c",
        name="Parada C",
        location=Coordinates(latitude=0.0, longitude=0.02),
        window=TimeWindow(start_time=time(9, 0), end_time=time(18, 0)),
        stay_duration_minutes=30,
        utility_score=10.0,
    )
    poi_d = POI(
        id="poi-d",
        name="Parada D",
        location=Coordinates(latitude=0.0, longitude=0.04),
        window=TimeWindow(start_time=time(9, 0), end_time=time(18, 0)),
        stay_duration_minutes=30,
        utility_score=10.0,
    )

    solver = OPTWSolver(transit_speed_kmh=20.0)
    itinerary = solver.solve(
        start_location=start_loc,
        end_location=end_loc,
        window=TimeWindow(start_time=time(9, 0), end_time=time(18, 0)),
        candidates=[poi_a, poi_b, poi_c, poi_d],
    )

    assert len(itinerary.stops) == 4
    assert itinerary.total_utility == 40.0

    # Ensure monotonic sequence along longitude due to 2-opt / swap untangling
    longitudes = [s.poi.location.longitude for s in itinerary.stops]
    assert longitudes == sorted(longitudes)


def test_optw_solver_blocks_attractions_during_reserved_slots() -> None:
    """Verifica que nenhuma parada sobrepõe slots reservados."""
    start_loc = Coordinates(latitude=-23.5505, longitude=-46.6333)
    end_loc = Coordinates(latitude=-23.5600, longitude=-46.6500)

    # 4 reserved slots: almoço, café, wine bar, jantar
    lunch = TimeWindow(start_time=time(12, 30), end_time=time(14, 0))
    coffee = TimeWindow(start_time=time(15, 30), end_time=time(16, 15))
    wine = TimeWindow(start_time=time(18, 0), end_time=time(19, 15))
    dinner = TimeWindow(start_time=time(19, 30), end_time=time(21, 0))
    reserved = [lunch, coffee, wine, dinner]

    # POIs spanning throughout the day
    pois = [
        POI(
            id=f"poi-{i}",
            name=f"Atração {i}",
            location=Coordinates(latitude=-23.5510 - (i * 0.005), longitude=-46.6350 - (i * 0.005)),
            window=TimeWindow(start_time=time(9, 0), end_time=time(21, 0)),
            stay_duration_minutes=60,
            utility_score=5.0 + i,
        )
        for i in range(6)
    ]

    solver = OPTWSolver()
    itinerary = solver.solve(
        start_location=start_loc,
        end_location=end_loc,
        window=TimeWindow(start_time=time(9, 0), end_time=time(21, 30)),
        candidates=pois,
        reserved_slots=reserved,
    )

    assert len(itinerary.stops) >= 2

    # Check zero overlap with any reserved slot
    for stop in itinerary.stops:
        for slot in reserved:
            overlap = max(stop.arrival_time, slot.start_time) < min(
                stop.departure_time, slot.end_time
            )
            assert not overlap, (
                f"Parada {stop.poi.name} ({stop.arrival_time}-{stop.departure_time}) "
                f"sobrepõe slot reservado ({slot.start_time}-{slot.end_time})"
            )
