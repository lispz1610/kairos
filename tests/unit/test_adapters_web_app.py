"""Testes unitários de construção de eventos de contingência no app web.

Construção dos Eventos de Contingência a partir dos pedidos de Evento.
"""

from datetime import datetime, time

from src.adapters.web.app import ContingencyEventRequest, _to_domain_event
from src.adapters.web.contingency import orchestrate_trip_replan, to_domain_event
from src.core.domain.events import (
    ClosureEvent,
    DelayEvent,
    DurationAdjustmentEvent,
    SkipStopEvent,
)
from src.core.domain.models import POI, Itinerary, RouteStop, TimeWindow


def test_to_domain_event_receives_accumulated_current_time() -> None:
    """Verifica passagem de current_time acumulado ao DelayEvent.

    ``_to_domain_event`` passa o ``current_time`` acumulado — e não
    ``request.current_time`` — ao ``DelayEvent``: os Eventos subsequentes
    consideram o avanço do ``current_time`` dos Eventos anteriores.
    """
    event_req = ContingencyEventRequest(type="delay", delay_minutes=15)
    current_time = datetime(2026, 11, 21, 10, 0)

    event = _to_domain_event(event_req, current_time=current_time, coordinates=(-23.5505, -46.6333))

    assert isinstance(event, DelayEvent)
    assert event.current_time == current_time
    assert event.delay_minutes == 15


def test_to_domain_event_maps_closure_skip_and_duration_adjustment() -> None:
    """Verifica conversão dos demais tipos de Evento de Contingência."""
    current_time = datetime(2026, 11, 21, 10, 0)
    coords = (-23.5505, -46.6333)

    closure = to_domain_event(
        ContingencyEventRequest(type="closure", poi_id="POI-1"),
        current_time=current_time,
        coordinates=coords,
    )
    skip = to_domain_event(
        ContingencyEventRequest(type="skip", poi_id="POI-2"),
        current_time=current_time,
        coordinates=coords,
    )
    adjustment = to_domain_event(
        ContingencyEventRequest(
            type="duration_adjustment", poi_id="POI-3", new_duration_minutes=45
        ),
        current_time=current_time,
        coordinates=coords,
    )

    assert closure == ClosureEvent(poi_id="POI-1")
    assert skip == SkipStopEvent(poi_id="POI-2")
    assert adjustment == DurationAdjustmentEvent(poi_id="POI-3", new_duration_minutes=45)


def test_orchestrate_trip_replan_applies_events_in_sequence() -> None:
    """Verifica orquestração direta de Eventos de Contingência sem camada HTTP."""
    coords = (-23.5505, -46.6333)
    window = TimeWindow(start=time(8, 0), end=time(20, 0))
    poi_a = POI(
        id="POI-A",
        name="Ponto A",
        coordinates=coords,
        operating_window=TimeWindow(start=time(9, 0), end=time(12, 0)),
        utility_score=9.0,
    )
    poi_b = POI(
        id="POI-B",
        name="Ponto B",
        coordinates=coords,
        operating_window=TimeWindow(start=time(9, 0), end=time(12, 0)),
        utility_score=8.0,
    )
    itinerary = Itinerary(
        stops=[
            RouteStop(poi=poi_a, start=datetime(2026, 11, 21, 9, 0), duration_minutes=30),
            RouteStop(poi=poi_b, start=datetime(2026, 11, 21, 10, 0), duration_minutes=30),
        ]
    )

    result = orchestrate_trip_replan(
        itinerary=itinerary,
        availability_window=window,
        current_time=datetime(2026, 11, 21, 9, 0),
        current_coordinate=coords,
        events=[
            ContingencyEventRequest(type="delay", delay_minutes=15),
            ContingencyEventRequest(type="closure", poi_id="POI-B"),
        ],
    )

    assert result.preserved_pois == ["POI-A"]
    assert result.removed_pois == ["POI-B"]
    assert result.intercity_risk_alert is None
