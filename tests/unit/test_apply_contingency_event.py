"""Testes unitários do mapeador ``apply_contingency_event`` (ticket #38).

Cada teste é uma asserção lógica sobre o contrato público do mapeador: um
Evento de Contingência de entrada e as entradas de Replanejamento que ele
mapeia — ``(new_current_time, closed_pois, skipped_pois,
adjusted_duration_minutes)``.
"""

from datetime import datetime, time

from src.adapters.web.contingency import apply_contingency_event
from src.core.domain.events import (
    ClosureEvent,
    DelayEvent,
    DurationAdjustmentEvent,
    SkipStopEvent,
)
from src.core.domain.models import POI, Itinerary, RouteStop, TimeWindow

CURRENT_TIME = datetime(2026, 11, 20, 9, 0)


def _day() -> Itinerary:
    """Roteiro de Dia de Viagem com um POI na Janela de Funcionamento ``[08:00, 12:00]``."""
    poi = POI(
        id="POI-001",
        name="Ponto de Interesse 001",
        coordinates=(-23.5505, -46.6333),
        operating_window=TimeWindow(start=time(8, 0), end=time(12, 0)),
        utility_score=5.0,
    )
    return Itinerary(
        stops=[RouteStop(poi=poi, start=datetime(2026, 11, 20, 9, 0), duration_minutes=30)]
    )


def test_delay_event_advances_current_time_by_the_delay_minutes():
    """Verifica que DelayEvent avança o horário atual pelos minutos de atraso."""
    event = DelayEvent(
        delay_minutes=20, current_time=CURRENT_TIME, coordinates=(-23.5505, -46.6333)
    )

    new_current_time, _, _, _ = apply_contingency_event(_day(), CURRENT_TIME, event)

    assert new_current_time == datetime(2026, 11, 20, 9, 20)


def test_closure_event_maps_to_the_closed_poi():
    """Verifica que ClosureEvent mapeia para a lista de POIs fechados."""
    event = ClosureEvent(poi_id="POI-001")

    _, closed_pois, _, _ = apply_contingency_event(_day(), CURRENT_TIME, event)

    assert closed_pois == ["POI-001"]


def test_skip_stop_event_maps_to_the_skipped_poi():
    """Verifica que SkipStopEvent mapeia para a lista de POIs pulados."""
    event = SkipStopEvent(poi_id="POI-001")

    _, _, skipped_pois, _ = apply_contingency_event(_day(), CURRENT_TIME, event)

    assert skipped_pois == ["POI-001"]


def test_duration_adjustment_event_maps_to_the_adjusted_duration():
    """Verifica que DurationAdjustmentEvent mapeia para a duração ajustada."""
    event = DurationAdjustmentEvent(poi_id="POI-001", new_duration_minutes=60)

    _, _, _, adjusted_minutes = apply_contingency_event(_day(), CURRENT_TIME, event)

    assert adjusted_minutes == 60
