"""Testes unitários do ``ReplanningService`` (#37).

``ReplanningService.replan`` cobre o contrato do ticket #37:

- AC1: Paradas até ``current_time`` preservadas como histórico do Roteiro.
- AC2: A janela restante é reotimizada via ``OPTWSolver``, respeitando
  Slots de Refeição futuros já reservados.
- AC3: Teto seguro da Conexão Interurbana aplicado no último dia da etapa.
- AC4: Alerta de risco com déficit em minutos quando o retorno/embarque
  não couber antes do limite.
- AC5: Metadados estruturados: POIs preservados, removidos/substituídos e
  alerta de risco.
- AC6: POIs fechados/pulados excluídos do Roteiro replanejado.

Cada teste é uma asserção lógica sobre a interface pública
``ReplanningService.replan``: seus contratos de entrada e saída.
"""

from datetime import datetime, time, timedelta

import hypothesis.strategies as st
from hypothesis import given

from src.core.domain.models import (
    InterCityConnection,
    Itinerary,
    POI,
    RouteStop,
    TimeWindow,
)
from src.core.services.replanning import ReplanningService
from src.core.services.schedule import ScheduleService


def _make_poi(poi_id, opening, closing, utility_score=5.0):
    """Construtor de POIs com Janela de Funcionamento ``[opening, closing]``."""
    return POI(
        id=poi_id,
        name=f"Ponto de Interesse {poi_id}",
        coordinates=(-23.5505, -46.6333),
        operating_window=TimeWindow(start=opening, end=closing),
        utility_score=utility_score,
    )


def _stop(poi, start, duration_minutes=30):
    """Visita ao POI: ``start`` e Tempo de Permanência em minutos."""
    return RouteStop(poi=poi, start=start, duration_minutes=duration_minutes)


def _replan(**overrides):
    """Invoca ``ReplanningService.replan`` com argumentos comuns aos testes."""
    arguments = {
        "travel_time_minutes": 15.0,
        "coordinates": (-23.5505, -46.6333),
    }
    arguments.update(overrides)
    return ReplanningService.replan(**arguments)


def test_ac1_paradas_ate_current_time_preservadas_como_historico():
    availability = TimeWindow(start=time(8, 0), end=time(20, 0))
    poi_a = _make_poi("POI-A", time(9, 0), time(12, 0), utility_score=9.0)
    poi_b = _make_poi("POI-B", time(9, 0), time(12, 0), utility_score=8.0)
    poi_c = _make_poi("POI-C", time(9, 0), time(12, 0), utility_score=7.0)
    current_time = datetime(2026, 11, 20, 10, 0)
    itinerary = Itinerary(
        stops=[
            _stop(poi_a, datetime(2026, 11, 20, 9, 0), duration_minutes=60),
            _stop(poi_b, datetime(2026, 11, 20, 10, 0), duration_minutes=30),
            _stop(poi_c, datetime(2026, 11, 20, 11, 0), duration_minutes=30),
        ]
    )

    result = _replan(
        itinerary=itinerary,
        availability_window=availability,
        current_time=current_time,
    )

    assert result.itinerary.stops[:2] == itinerary.stops[:2]
    assert result.preserved_pois == ["POI-A", "POI-B"]


def test_ac2_janela_restante_reotimizada_via_optw_dentro_da_disponibilidade():
    availability = TimeWindow(start=time(8, 0), end=time(20, 0))
    poi_a = _make_poi("POI-A", time(9, 0), time(12, 0), utility_score=9.0)
    poi_b = _make_poi("POI-B", time(9, 0), time(12, 0), utility_score=8.0)
    poi_c = _make_poi("POI-C", time(9, 0), time(12, 0), utility_score=7.0)
    current_time = datetime(2026, 11, 20, 9, 0)
    itinerary = Itinerary(
        stops=[
            _stop(poi_a, datetime(2026, 11, 20, 9, 30), duration_minutes=30),
            _stop(poi_b, datetime(2026, 11, 20, 10, 30), duration_minutes=30),
            _stop(poi_c, datetime(2026, 11, 20, 11, 30), duration_minutes=30),
        ]
    )

    result = _replan(
        itinerary=itinerary,
        availability_window=availability,
        current_time=current_time,
    )

    assert result.preserved_pois == []
    assert result.intercity_risk_alert is None
    assert result.itinerary.stops
    assert ScheduleService.validate_itinerary(result.itinerary, availability) == []
    assert all(current_time <= stop.start for stop in result.itinerary.stops)
    assert all(
        stop.poi.id in {"POI-A", "POI-B", "POI-C"}
        for stop in result.itinerary.stops
    )


def test_ac2_slots_de_refeicao_futuros_ja_reservados_sao_preservados():
    availability = TimeWindow(start=time(8, 0), end=time(20, 0))
    poi_a = _make_poi("POI-A", time(9, 0), time(12, 0), utility_score=8.0)
    poi_b = _make_poi("POI-B", time(9, 0), time(12, 0), utility_score=9.0)
    poi_c = _make_poi("POI-C", time(11, 0), time(12, 0), utility_score=7.0)
    current_time = datetime(2026, 11, 20, 9, 0)
    itinerary = Itinerary(
        stops=[
            _stop(poi_a, datetime(2026, 11, 20, 9, 30), duration_minutes=30),
            _stop(poi_b, datetime(2026, 11, 20, 10, 30), duration_minutes=30),
        ]
    )
    reserved_stop = _stop(poi_c, datetime(2026, 11, 20, 11, 0), 30)

    result = _replan(
        itinerary=itinerary,
        availability_window=availability,
        current_time=current_time,
        reserved_future_stops=[reserved_stop],
    )

    assert reserved_stop in result.itinerary.stops
    assert "POI-C" in result.preserved_pois
    assert ScheduleService.validate_itinerary(result.itinerary, availability) == []
    # Roteiro cronológico: POIs agendados pelo solver antes do Slot
    # permanecem antes dele.
    assert result.itinerary.stops == sorted(
        result.itinerary.stops, key=lambda stop: stop.start
    )


def test_replan_keeps_free_window_before_future_reserved_slot() -> None:
    """Slot de Refeição reservado no futuro: a janela livre ANTES do Slot continua disponível ao replano."""
    availability = TimeWindow(start=time(9, 0), end=time(20, 0))
    poi_a = _make_poi("POI-A", time(9, 0), time(12, 0), utility_score=9.0)
    slot_poi = _make_poi("POI-SLOT", time(11, 0), time(11, 30), utility_score=5.0)
    slot = _stop(slot_poi, datetime(2026, 11, 20, 11, 0), 30)  # Slot reservado 11:00–11:30
    day = Itinerary(stops=[_stop(poi_a, datetime(2026, 11, 20, 9, 30), 30)])
    result = _replan(
        itinerary=day,
        availability_window=availability,
        current_time=datetime(2026, 11, 20, 9, 0),
        reserved_future_stops=[slot],
    )
    # POI-A deve ser incluído agendado na janela livre 09:00–11:00 (antes do Slot).
    assert any(
        stop.poi.id == "POI-A" and stop.start.time() < time(11, 0)
        for stop in result.itinerary.stops
    )


def test_replan_keeps_free_window_before_future_reserved_slot() -> None:
    """Slot de Refeição reservado no futuro: a janela livre ANTES do Slot continua disponível ao replano."""
    availability = TimeWindow(start=time(9, 0), end=time(20, 0))
    poi_a = _make_poi("POI-A", time(9, 0), time(12, 0), utility_score=9.0)
    slot_poi = _make_poi("POI-SLOT", time(11, 0), time(11, 30), utility_score=5.0)
    slot = _stop(slot_poi, datetime(2026, 11, 20, 11, 0), 30)  # Slot reservado 11:00–11:30
    day = Itinerary(stops=[_stop(poi_a, datetime(2026, 11, 20, 9, 30), 30)])
    result = _replan(
        itinerary=day,
        availability_window=availability,
        current_time=datetime(2026, 11, 20, 9, 0),
        reserved_future_stops=[slot],
    )
    # POI-A deve ser incluído agendado na janela livre 09:00–11:00 (antes do Slot).
    assert any(
        stop.poi.id == "POI-A" and stop.start.time() < time(11, 0)
        for stop in result.itinerary.stops
    )


def test_duration_adjustment_applies_to_future_poi_scheduled_later() -> None:
    availability = TimeWindow(start=time(8, 0), end=time(20, 0))
    poi_a = _make_poi("POI-A", time(9, 0), time(12, 0), utility_score=9.0)
    poi_d = _make_poi("POI-D", time(11, 0), time(13, 0), utility_score=8.0)
    current_time = datetime(2026, 11, 20, 9, 0)
    itinerary = Itinerary(
        stops=[_stop(poi_a, datetime(2026, 11, 20, 9, 0), duration_minutes=30)]
    )
    reserved_stop = _stop(poi_d, datetime(2026, 11, 20, 11, 0), 30)

    result = _replan(
        itinerary=itinerary,
        availability_window=availability,
        current_time=current_time,
        reserved_future_stops=[reserved_stop],
        duration_adjustments={"POI-D": 60},
    )

    stop_d = next(
        stop for stop in result.itinerary.stops if stop.poi.id == "POI-D"
    )
    assert stop_d.start == reserved_stop.start
    assert stop_d.duration_minutes == 60
    assert "POI-D" in result.preserved_pois


def test_ac3_teto_seguro_da_conexao_interurbana_aplicado_no_ultimo_dia():
    availability = TimeWindow(start=time(8, 0), end=time(18, 0))
    pois = [
        _make_poi(poi_id, time(8, 0), time(23, 0), utility_score=utility_score)
        for poi_id, utility_score in zip(
            ["POI-1", "POI-2", "POI-3", "POI-4", "POI-5", "POI-6"],
            [9.0, 8.0, 7.0, 6.0, 5.0, 4.0],
        )
    ]
    connection = InterCityConnection(
        origin="A",
        destination="B",
        departure_datetime=datetime(2026, 11, 20, 15, 30),
        modal="flying",
    )
    limit = (
        connection.departure_datetime
        - timedelta(minutes=connection.boarding_cutoff_minutes)
    ).time()
    current_time = datetime(2026, 11, 20, 9, 0)
    itinerary = Itinerary(
        stops=[
            _stop(
                poi,
                datetime(2026, 11, 20, 9, 30) + timedelta(minutes=30 * index),
                duration_minutes=30,
            )
            for index, poi in enumerate(pois)
        ]
    )

    result = _replan(
        itinerary=itinerary,
        availability_window=availability,
        current_time=current_time,
        travel_time_minutes=60.0,
        intercity_connection=connection,
    )

    assert result.intercity_risk_alert is None
    assert result.itinerary.stops
    assert ScheduleService.validate_itinerary(result.itinerary, availability) == []
    for stop in result.itinerary.stops:
        visit_end = stop.start + timedelta(minutes=stop.duration_minutes)
        assert visit_end.time() <= limit


def test_ac4_alerta_de_risco_com_deficit_em_minutos_quando_embarque_nao_cabe():
    availability = TimeWindow(start=time(8, 0), end=time(18, 0))
    poi_a = _make_poi("POI-A", time(9, 0), time(12, 0), utility_score=9.0)
    connection = InterCityConnection(
        origin="A",
        destination="B",
        departure_datetime=datetime(2026, 11, 20, 15, 0),
        boarding_cutoff_minutes=30,
    )
    current_time = datetime(2026, 11, 20, 14, 45)
    itinerary = Itinerary(stops=[_stop(poi_a, datetime(2026, 11, 20, 14, 0), 30)])

    result = _replan(
        itinerary=itinerary,
        availability_window=availability,
        current_time=current_time,
        intercity_connection=connection,
    )

    assert result.intercity_risk_alert is not None
    assert result.intercity_risk_alert.deficit_minutes == 15
    assert result.itinerary.stops[0] == itinerary.stops[0]


def test_ac5_metadados_preservados_removidos_e_alerta_de_risco():
    availability = TimeWindow(start=time(8, 0), end=time(12, 0))
    poi_a = _make_poi("POI-A", time(8, 0), time(9, 0), utility_score=9.0)
    poi_b = _make_poi("POI-B", time(9, 0), time(11, 0), utility_score=8.0)
    poi_c = _make_poi("POI-C", time(9, 0), time(11, 0), utility_score=7.0)
    poi_d = _make_poi("POI-D", time(11, 30), time(12, 0), utility_score=6.0)
    current_time = datetime(2026, 11, 20, 8, 30)
    itinerary = Itinerary(
        stops=[
            _stop(poi_a, datetime(2026, 11, 20, 8, 0), duration_minutes=60),
            _stop(poi_b, datetime(2026, 11, 20, 9, 30), duration_minutes=30),
            _stop(poi_c, datetime(2026, 11, 20, 10, 0), duration_minutes=30),
            _stop(poi_d, datetime(2026, 11, 20, 10, 30), duration_minutes=30),
        ]
    )

    result = _replan(
        itinerary=itinerary,
        availability_window=availability,
        current_time=current_time,
        excluded_pois=["POI-C"],
    )

    assert result.preserved_pois == ["POI-A"]
    assert result.removed_pois == ["POI-C", "POI-D"]
    assert result.intercity_risk_alert is None
    assert ScheduleService.validate_itinerary(result.itinerary, availability) == []


def test_ac6_pois_fechados_ou_pulados_excluidos_do_roteiro_replano():
    availability = TimeWindow(start=time(8, 0), end=time(12, 0))
    poi_a = _make_poi("POI-A", time(8, 0), time(9, 0), utility_score=9.0)
    poi_b = _make_poi("POI-B", time(9, 0), time(11, 0), utility_score=8.0)
    poi_c = _make_poi("POI-C", time(9, 0), time(11, 0), utility_score=7.0)
    current_time = datetime(2026, 11, 20, 8, 30)
    itinerary = Itinerary(
        stops=[
            _stop(poi_a, datetime(2026, 11, 20, 8, 0), duration_minutes=60),
            _stop(poi_b, datetime(2026, 11, 20, 9, 0), duration_minutes=30),
            _stop(poi_c, datetime(2026, 11, 20, 9, 30), duration_minutes=30),
        ]
    )

    result = _replan(
        itinerary=itinerary,
        availability_window=availability,
        current_time=current_time,
        excluded_pois=["POI-C"],
    )

    assert "POI-C" not in [stop.poi.id for stop in result.itinerary.stops]
    assert "POI-C" in result.removed_pois


def _stops_at_or_before(itinerary, current_time):
    """Paradas até o ``current_time``: a definição de histórico do Roteiro."""
    return [stop for stop in itinerary.stops if stop.start <= current_time]


@st.composite
def _replan_inputs(draw):
    """Gera ``(itinerary, current_time, availability_window)`` para os
    invariantes do Replanejamento: Roteiro cronológico com visitas dentro da
    Janela de Funcionamento, e ``current_time`` dentro da Janela de
    Disponibilidade."""
    availability = TimeWindow(start=time(8, 0), end=time(20, 0))
    start_minutes = sorted(
        draw(
            st.lists(st.integers(min_value=480, max_value=1140), min_size=0, max_size=8)
        )
    )
    stops = [
        _stop(
            _make_poi(f"POI-{index:03d}", time(8, 0), time(20, 0), utility_score=5.0),
            datetime(2026, 11, 20) + timedelta(minutes=start_minute),
            draw(st.integers(min_value=0, max_value=30)),
        )
        for index, start_minute in enumerate(start_minutes)
    ]
    current_time = datetime(2026, 11, 20) + timedelta(
        minutes=draw(st.integers(min_value=480, max_value=1200))
    )
    return Itinerary(stops=stops), current_time, availability


@given(_replan_inputs())
def test_propriedade_nenhuma_parada_passada_alterada(replan_inputs):
    itinerary, current_time, availability = replan_inputs
    preserved = _stops_at_or_before(itinerary, current_time)

    result = _replan(
        itinerary=itinerary,
        availability_window=availability,
        current_time=current_time,
    )

    assert result.itinerary.stops[: len(preserved)] == preserved


@given(_replan_inputs())
def test_propriedade_janelas_de_funcionamento_e_disponibilidade_nao_violadas(
    replan_inputs,
):
    itinerary, current_time, availability = replan_inputs

    result = _replan(
        itinerary=itinerary,
        availability_window=availability,
        current_time=current_time,
    )

    assert ScheduleService.validate_itinerary(result.itinerary, availability) == []
