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
from hypothesis import given

from src.core.domain.models import POI, Itinerary, TimeWindow
from src.core.services.schedule import ScheduleService
from src.core.solvers.optw import OPTWSolver


def _make_poi(poi_id, opening, closing, utility_score):
    return POI(
        id=poi_id,
        name=f"Ponto de Interesse {poi_id}",
        coordinates=(-23.5505, -46.6333),
        operating_window=TimeWindow(start=opening, end=closing),
        utility_score=utility_score,
    )


def _assert_invariants(itinerary, availability_window):
    """Invariantes universais da AC2: nenhuma visita fora do Horário de
    Funcionamento do POI e do término do intervalo da Janela de Disponibilidade;
    o Roteiro está em ordem cronológica e sem desvios reportados por
    ``ScheduleService``."""
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
    availability = TimeWindow(start=time(8, 0), end=time(18, 0))
    start_time = datetime(2026, 11, 20, 9, 0)
    poi_a = _make_poi("POI-A", time(9, 0), time(10, 30), utility_score=10.0)
    poi_b = _make_poi("POI-B", time(9, 30), time(11, 0), utility_score=1.0)

    itinerary = OPTWSolver.solve(
        [poi_a, poi_b], availability, travel_time_minutes=15, start_time=start_time
    )

    assert [stop.poi.id for stop in itinerary.stops] == ["POI-A"]
    _assert_invariants(itinerary, availability)


def test_sem_pois_candidatos_retorna_roteiro_vazio():
    availability = TimeWindow(start=time(8, 0), end=time(18, 0))
    start_time = datetime(2026, 11, 20, 9, 0)

    itinerary = OPTWSolver.solve(
        [], availability, travel_time_minutes=15, start_time=start_time
    )

    assert itinerary == Itinerary(stops=[])
    _assert_invariants(itinerary, availability)


def test_rota_visita_todos_os_pois_candidatos_quando_viáveis():
    availability = TimeWindow(start=time(8, 0), end=time(20, 0))
    start_time = datetime(2026, 11, 20, 9, 0)
    poi_a = _make_poi("POI-A", time(9, 0), time(12, 0), utility_score=5.0)
    poi_b = _make_poi("POI-B", time(9, 0), time(12, 0), utility_score=3.0)

    itinerary = OPTWSolver.solve(
        [poi_a, poi_b], availability, travel_time_minutes=0, start_time=start_time
    )

    assert {stop.poi.id for stop in itinerary.stops} == {"POI-A", "POI-B"}
    _assert_invariants(itinerary, availability)


def test_visita_fora_do_horario_de_funcionamento_não_é_agendada():
    availability = TimeWindow(start=time(8, 0), end=time(18, 0))
    start_time = datetime(2026, 11, 20, 9, 0)
    poi = _make_poi("POI-A", time(9, 30), time(10, 0), utility_score=5.0)

    itinerary = OPTWSolver.solve(
        [poi], availability, travel_time_minutes=0, start_time=start_time
    )

    assert itinerary.stops == []
    _assert_invariants(itinerary, availability)


def test_janela_de_disponibilidade_limitante_bloqueia_visita():
    availability = TimeWindow(start=time(8, 0), end=time(8, 20))
    start_time = datetime(2026, 11, 20, 8, 0)
    poi_a = _make_poi("POI-01", time(8, 0), time(23, 0), utility_score=10.0)
    poi_b = _make_poi("POI-02", time(8, 0), time(23, 0), utility_score=1.0)

    itinerary = OPTWSolver.solve(
        [poi_a, poi_b], availability, travel_time_minutes=30, start_time=start_time
    )

    assert [stop.poi.id for stop in itinerary.stops] == ["POI-01"]
    _assert_invariants(itinerary, availability)


def test_itinerário_está_em_ordem_cronológica():
    availability = TimeWindow(start=time(8, 0), end=time(20, 0))
    start_time = datetime(2026, 11, 20, 9, 0)
    poi_a = _make_poi("POI-A", time(9, 0), time(12, 0), utility_score=5.0)
    poi_b = _make_poi("POI-B", time(9, 0), time(12, 0), utility_score=3.0)

    itinerary = OPTWSolver.solve(
        [poi_a, poi_b], availability, travel_time_minutes=30, start_time=start_time
    )

    assert len(itinerary.stops) == 2
    _assert_invariants(itinerary, availability)


def test_início_padrão_usa_o_início_da_janela_de_disponibilidade():
    availability = TimeWindow(start=time(9, 0), end=time(12, 0))
    poi_a = _make_poi("POI-A", time(9, 0), time(11, 0), utility_score=5.0)

    itinerary = OPTWSolver.solve([poi_a], availability, travel_time_minutes=15)

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
    availability = TimeWindow(start=time(8, 0), end=time(20, 0))
    start_time = datetime(2026, 11, 20, 8, 0)

    itinerary = OPTWSolver.solve(
        pois, availability, float(travel_minutes), start_time=start_time
    )

    _assert_invariants(itinerary, availability)


@given(
    st.lists(_poi_strategy(), min_size=0, max_size=8),
    st.integers(min_value=0, max_value=30),
)
def test_propriedade_invariantes_ac2_início_padrão(pois, travel_minutes):
    availability = TimeWindow(start=time(8, 0), end=time(20, 0))

    itinerary = OPTWSolver.solve(pois, availability, float(travel_minutes))

    _assert_invariants(itinerary, availability)
