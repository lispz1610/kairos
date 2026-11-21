"""Mapeamento de Eventos de Contingência para as entradas de Replanejamento.

``apply_contingency_event`` é o mapeador puro do ticket #38: dado o Roteiro do
Dia de Viagem, o horário atual e um Evento de Contingência (de #35), devolve
``(new_current_time, closed_pois, skipped_pois, adjusted_duration_minutes)``
— os valores que alimentam ``ReplanningService.replan``.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.core.domain.events import (
    ClosureEvent,
    DelayEvent,
    DurationAdjustmentEvent,
    SkipStopEvent,
)
from src.core.domain.models import Itinerary

__all__ = ["ContingencyEvent", "apply_contingency_event"]

ContingencyEvent = DelayEvent | ClosureEvent | SkipStopEvent | DurationAdjustmentEvent
"""Union dos Eventos de Contingência aplicáveis ao Roteiro do Dia de Viagem."""


def apply_contingency_event(
    day: Itinerary,
    current_time: datetime,
    event: ContingencyEvent,
) -> tuple[datetime, list[str], list[str], int | None]:
    """Mapear um Evento de Contingência para as entradas de Replanejamento do Roteiro.

    Args:
        day: Roteiro do Dia de Viagem ao qual o Evento se aplica.
        current_time: Horário atual do Dia de Viagem antes do Evento.
        event: Evento de Contingência aplicado.

    Returns:
        Tupla ``(new_current_time, closed_pois, skipped_pois,
        adjusted_duration_minutes)``: o horário atual efetivo após o Evento —
        ``current_time + delay_minutes`` para ``DelayEvent`` — e as
        identificações dos POIs fechados/pulados, que alimentam a entrada
        ``excluded_pois`` do ``ReplanningService.replan``; o novo Tempo de
        Permanência do POI ajustado, quando houver.
    """
    if isinstance(event, DelayEvent):
        return current_time + timedelta(minutes=event.delay_minutes), [], [], None
    if isinstance(event, ClosureEvent):
        return current_time, [event.poi_id], [], None
    if isinstance(event, SkipStopEvent):
        return current_time, [], [event.poi_id], None
    return current_time, [], [], event.new_duration_minutes
