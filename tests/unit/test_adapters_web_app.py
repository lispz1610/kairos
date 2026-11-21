"""Testes unitários de construção de eventos de contingência no app web.

Construção dos Eventos de Contingência a partir dos pedidos de Evento.
"""

from datetime import datetime

from src.adapters.web.app import ContingencyEventRequest, _to_domain_event
from src.core.domain.events import DelayEvent


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
