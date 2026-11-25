"""Testes unitários e de propriedade do ``OPTWSolver`` (#36).

``OPTWSolver.solve`` implementa a heurística construtiva de inserção gulosa
ponderada pela Pontuação de Utilidade / Custo Marginal de Tempo de ADR 0001,
seguida de busca local de swaps de paradas e 2-opt:

- AC1: ``OPTWSolver`` produz um Roteiro respeitando os Horários de Funcionamento
  dos POIs.
- AC2: invariantes universais: nenhuma visita fora do Horário de Funcionamento
  do POI; tempo total dentro da Janela de Disponibilidade.
- AC3: testes de propriedade (``hypothesis``) garantindo as invariantes AC2.

Visita de Tempo de Permanência zero: o modelo ``POI`` não fornece Tempo de
Permanência configurado, então o solver emite ``RouteStop`` com
``duration_minutes`` 0 — o visitante descansa nulo no interior do POI e o
constraint de Janela de Funcionamento aplica ao horário da visita.
"""

from datetime import datetime, time, timedelta

import hypothesis.strategies as st
import pytest
from hypothesis import given

from src.core.domain.models import POI, Accommodation, Coordinates, Itinerary, TimeWindow
from src.core.services.preferences import PreferencesService
from src.core.services.schedule import ScheduleService
from src.core.solvers.optw import OPTWSolver


def _make_poi(poi_id: str, opening: time, closing: time, utility_score: float) -> POI:
    return POI(
        id=poi_id,
        name=f"Ponto de Interesse {poi_id}",
        coordinates=(-23.5505, -46.6333),
        operating_window=TimeWindow(start=opening, end=closing),
        utility_score=utility_score,
    )


def _assert_invariants(itinerary: Itinerary, availability_window: TimeWindow) -> None:
    """Valida as invariantes universais da AC2.

    Nenhuma visita fora do Horário de Funcionamento do POI e do término do
    intervalo da Janela de Disponibilidade; o Roteiro está em ordem cronológica
    e sem desvios reportados por ``ScheduleService``.
    """
    for stop in itinerary.stops:
        visit_end = stop.start + timedelta(minutes=stop.duration_minutes)
        operating_window = stop.poi.operating_window
        assert stop.start.time() >= operating_window.start
        assert visit_end.time() <= operating_window.end
        assert stop.start.time() >= availability_window.start
        assert visit_end.time() <= availability_window.end
    starts = [stop.start for stop in itinerary.stops]
    assert starts == sorted(starts)
    assert ScheduleService.validate_itinerary(itinerary, availability_window) == []


def test_ac1_ac2_rota_dentro_do_horario_de_funcionamento_e_da_janela():
    """Valida que a rota respeita horários de funcionamento e janela de disponibilidade."""
    availability = TimeWindow(start=time(8, 0), end=time(18, 0))
    start_time = datetime(2026, 11, 20, 9, 0)
    poi_a = _make_poi("POI-A", time(9, 0), time(10, 30), utility_score=10.0)
    poi_b = _make_poi("POI-B", time(9, 30), time(11, 0), utility_score=1.0)

    itinerary = OPTWSolver.replan_remaining(
        [poi_a, poi_b], availability, travel_time_minutes=15, start_time=start_time
    )

    assert [stop.poi.id for stop in itinerary.stops] == ["POI-A"]
    _assert_invariants(itinerary, availability)


def test_sem_pois_candidatos_retorna_roteiro_vazio():
    """Valida que lista vazia de POIs retorna roteiro vazio."""
    availability = TimeWindow(start=time(8, 0), end=time(18, 0))
    start_time = datetime(2026, 11, 20, 9, 0)

    itinerary = OPTWSolver.replan_remaining(
        [], availability, travel_time_minutes=15, start_time=start_time
    )

    assert itinerary == Itinerary(stops=[])
    _assert_invariants(itinerary, availability)


def test_rota_visita_todos_os_pois_candidatos_quando_viáveis():
    """Valida visitação de todos os POIs quando viáveis."""
    availability = TimeWindow(start=time(8, 0), end=time(20, 0))
    start_time = datetime(2026, 11, 20, 9, 0)
    poi_a = _make_poi("POI-A", time(9, 0), time(12, 0), utility_score=5.0)
    poi_b = _make_poi("POI-B", time(9, 0), time(12, 0), utility_score=3.0)

    itinerary = OPTWSolver.replan_remaining(
        [poi_a, poi_b], availability, travel_time_minutes=0, start_time=start_time
    )

    assert {stop.poi.id for stop in itinerary.stops} == {"POI-A", "POI-B"}
    _assert_invariants(itinerary, availability)


def test_visita_fora_do_horario_de_funcionamento_não_é_agendada():
    """Valida que POI fora do horário de funcionamento não é agendado."""
    availability = TimeWindow(start=time(8, 0), end=time(18, 0))
    start_time = datetime(2026, 11, 20, 9, 0)
    poi = _make_poi("POI-A", time(9, 30), time(10, 0), utility_score=5.0)

    itinerary = OPTWSolver.replan_remaining(
        [poi], availability, travel_time_minutes=0, start_time=start_time
    )

    assert itinerary.stops == []
    _assert_invariants(itinerary, availability)


def test_janela_de_disponibilidade_limitante_bloqueia_visita():
    """Valida que janela de disponibilidade limitante restringe visitas."""
    availability = TimeWindow(start=time(8, 0), end=time(8, 20))
    start_time = datetime(2026, 11, 20, 8, 0)
    poi_a = _make_poi("POI-01", time(8, 0), time(23, 0), utility_score=10.0)
    poi_b = _make_poi("POI-02", time(8, 0), time(23, 0), utility_score=1.0)
    poi_a.stay_duration_minutes = 15
    poi_b.stay_duration_minutes = 15

    itinerary = OPTWSolver.replan_remaining(
        [poi_a, poi_b], availability, travel_time_minutes=30, start_time=start_time
    )

    assert [stop.poi.id for stop in itinerary.stops] == ["POI-01"]
    _assert_invariants(itinerary, availability)


def test_itinerário_está_em_ordem_cronológica():
    """Valida que as paradas do roteiro seguem estrita ordem cronológica."""
    availability = TimeWindow(start=time(8, 0), end=time(20, 0))
    start_time = datetime(2026, 11, 20, 9, 0)
    poi_a = _make_poi("POI-A", time(9, 0), time(12, 0), utility_score=5.0)
    poi_b = _make_poi("POI-B", time(9, 0), time(12, 0), utility_score=3.0)

    itinerary = OPTWSolver.replan_remaining(
        [poi_a, poi_b], availability, travel_time_minutes=30, start_time=start_time
    )

    assert len(itinerary.stops) == 2
    _assert_invariants(itinerary, availability)


def test_início_padrão_usa_o_início_da_janela_de_disponibilidade():
    """Valida que a ausência de start_time adota o início da janela de disponibilidade."""
    availability = TimeWindow(start=time(9, 0), end=time(12, 0))
    poi_a = _make_poi("POI-A", time(9, 0), time(11, 0), utility_score=5.0)

    itinerary = OPTWSolver.replan_remaining([poi_a], availability, travel_time_minutes=15)

    assert itinerary.stops[0].poi.id == "POI-A"
    assert itinerary.stops[0].start.time() == time(9, 0)
    _assert_invariants(itinerary, availability)


@st.composite
def _poi_strategy(draw):
    opening_hour = draw(st.integers(min_value=6, max_value=18))
    closing_hour = draw(st.integers(min_value=opening_hour + 1, max_value=23))
    poi_number = draw(st.integers(min_value=1, max_value=500))
    utility_score = float(draw(st.integers(min_value=0, max_value=10)))
    return _make_poi(
        f"POI-{poi_number:03d}",
        time(opening_hour),
        time(closing_hour),
        utility_score,
    )


@given(
    st.lists(_poi_strategy(), min_size=0, max_size=8),
    st.integers(min_value=0, max_value=30),
)
def test_propriedade_invariantes_ac2(pois, travel_minutes):
    """Teste de propriedade para as invariantes universais AC2 com start_time explícito."""
    availability = TimeWindow(start=time(8, 0), end=time(20, 0))
    start_time = datetime(2026, 11, 20, 8, 0)

    itinerary = OPTWSolver.replan_remaining(
        pois, availability, float(travel_minutes), start_time=start_time
    )

    _assert_invariants(itinerary, availability)


@given(
    st.lists(_poi_strategy(), min_size=0, max_size=8),
    st.integers(min_value=0, max_value=30),
)
def test_propriedade_invariantes_ac2_início_padrão(pois, travel_minutes):
    """Teste de propriedade para as invariantes universais AC2 com início padrão."""
    availability = TimeWindow(start=time(8, 0), end=time(20, 0))

    itinerary = OPTWSolver.replan_remaining(pois, availability, float(travel_minutes))

    _assert_invariants(itinerary, availability)


@pytest.mark.requirement("RF01", "RF03")
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

    solver = OPTWSolver(preferences_service=PreferencesService())
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
    """Verifica que a busca local 2-opt e troca desentrelaça a ordem dos Pontos de Interesse."""
    start_loc = Coordinates(latitude=0.0, longitude=0.0)
    end_loc = Coordinates(latitude=0.0, longitude=0.06)

    # Placing POIs in a geometry where greedy insertion order can be optimized by 2-opt/swap
    # Coordinates along a line: A(0.01), B(0.05), C(0.02), D(0.04)
    # If visited 0 -> B -> A -> D -> C -> end, total distance is much higher
    # than 0 -> A -> C -> D -> B -> end
    poi_a = POI(
        id="poi-a",
        name="Ponto de Interesse A",
        location=Coordinates(latitude=0.0, longitude=0.01),
        window=TimeWindow(start_time=time(9, 0), end_time=time(18, 0)),
        stay_duration_minutes=30,
        utility_score=10.0,
    )
    poi_b = POI(
        id="poi-b",
        name="Ponto de Interesse B",
        location=Coordinates(latitude=0.0, longitude=0.05),
        window=TimeWindow(start_time=time(9, 0), end_time=time(18, 0)),
        stay_duration_minutes=30,
        utility_score=10.0,
    )
    poi_c = POI(
        id="poi-c",
        name="Ponto de Interesse C",
        location=Coordinates(latitude=0.0, longitude=0.02),
        window=TimeWindow(start_time=time(9, 0), end_time=time(18, 0)),
        stay_duration_minutes=30,
        utility_score=10.0,
    )
    poi_d = POI(
        id="poi-d",
        name="Ponto de Interesse D",
        location=Coordinates(latitude=0.0, longitude=0.04),
        window=TimeWindow(start_time=time(9, 0), end_time=time(18, 0)),
        stay_duration_minutes=30,
        utility_score=10.0,
    )

    solver = OPTWSolver(
        preferences_service=PreferencesService(), transit_speed_kmh=20.0
    )
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


@pytest.mark.requirement("RF03")
def test_optw_solver_blocks_attractions_during_reserved_slots() -> None:
    """Verifica que nenhum Ponto de Interesse sobrepõe Slots de Refeição reservados."""
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

    solver = OPTWSolver(preferences_service=PreferencesService())
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
                f"Ponto de Interesse {stop.poi.name} ({stop.arrival_time}-{stop.departure_time}) "
                f"sobrepõe slot reservado ({slot.start_time}-{slot.end_time})"
            )
