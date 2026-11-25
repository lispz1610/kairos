"""Mapeamento de Eventos de Contingência para as entradas de Replanejamento.

``apply_contingency_event`` é o mapeador puro do ticket #38: dado o Roteiro do
Dia de Viagem, o horário atual e um Evento de Contingência (de #35), devolve
``(new_current_time, closed_pois, skipped_pois, adjusted_duration_minutes)``
— os valores que alimentam ``ReplanningService.replan``.

``to_domain_event`` e ``orchestrate_trip_replan`` isolam da camada HTTP a
conversão dos pedidos de Evento de Contingência e a orquestração sequencial do
Replanejamento.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Literal, Protocol

from src.core.domain.events import (
    ClosureEvent,
    DelayEvent,
    DurationAdjustmentEvent,
    SkipStopEvent,
)
from src.core.domain.models import (
    Coordinates,
    InterCityConnection,
    Itinerary,
    ItineraryStop,
    RouteStop,
    TimeWindow,
)
from src.core.services.replanning import ReplanningService, ReplanResult
from src.core.solvers.optw import DEFAULT_TRAVEL_TIME_MINUTES

__all__ = [
    "ContingencyEvent",
    "ContingencyEventInput",
    "apply_contingency_event",
    "orchestrate_trip_replan",
    "to_domain_event",
]

ContingencyEvent = DelayEvent | ClosureEvent | SkipStopEvent | DurationAdjustmentEvent
"""Union dos Eventos de Contingência aplicáveis ao Roteiro do Dia de Viagem."""


class ContingencyEventInput(Protocol):
    """Contrato estrutural para entrada de Evento de Contingência da camada HTTP."""

    @property
    def type(self) -> Literal["delay", "closure", "skip", "duration_adjustment"]:
        """Tipo do Evento de Contingência."""
        ...

    @property
    def poi_id(self) -> str | None:
        """Identificação do POI afetado pelo Evento, quando aplicável."""
        ...

    @property
    def delay_minutes(self) -> int | None:
        """Minutos de atraso a partir do horário atual (Evento ``delay``)."""
        ...

    @property
    def new_duration_minutes(self) -> int | None:
        """Novo Tempo de Permanência em minutos (Evento ``duration_adjustment``)."""
        ...


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


def _require_field[T](value: T | None, field_name: str, event_type: str) -> T:
    """Garantir que atributo obrigatório do Evento de Contingência não seja None."""
    if value is None:
        raise ValueError(
            f"Campo '{field_name}' é obrigatório para Evento '{event_type}'."
        )
    return value


def to_domain_event(
    event_req: ContingencyEventInput,
    current_time: datetime,
    coordinates: Coordinates,
) -> ContingencyEvent:
    """Construir o Evento de Contingência de domínio a partir da entrada HTTP."""
    if event_req.type == "delay":
        return DelayEvent(
            delay_minutes=_require_field(
                event_req.delay_minutes, "delay_minutes", event_req.type
            ),
            current_time=current_time,
            coordinates=coordinates,
        )
    if event_req.type == "closure":
        return ClosureEvent(
            poi_id=_require_field(event_req.poi_id, "poi_id", event_req.type)
        )
    if event_req.type == "skip":
        return SkipStopEvent(
            poi_id=_require_field(event_req.poi_id, "poi_id", event_req.type)
        )
    return DurationAdjustmentEvent(
        poi_id=_require_field(event_req.poi_id, "poi_id", event_req.type),
        new_duration_minutes=_require_field(
            event_req.new_duration_minutes, "new_duration_minutes", event_req.type
        ),
    )


def orchestrate_trip_replan(
    *,
    itinerary: Itinerary,
    availability_window: TimeWindow,
    current_time: datetime,
    current_coordinate: Coordinates,
    events: Sequence[ContingencyEventInput] = (),
    reserved_future_stops: Sequence[RouteStop | ItineraryStop] = (),
    reserved_meal_slots: Sequence[TimeWindow] = (),
    excluded_pois: Sequence[str] = (),
    intercity_connection: InterCityConnection | None = None,
    travel_time_minutes: float = DEFAULT_TRAVEL_TIME_MINUTES,
) -> ReplanResult:
    """Aplicar sequência de Eventos de Contingência e executar o Replanejamento."""
    effective_time = current_time
    event_closed_pois: list[str] = []
    event_skipped_pois: list[str] = []
    duration_adjustments: dict[str, int] = {}
    for event_req in events:
        event = to_domain_event(event_req, effective_time, current_coordinate)
        effective_time, event_closed, event_skipped, adjusted_duration = (
            apply_contingency_event(itinerary, effective_time, event)
        )
        event_closed_pois.extend(event_closed)
        event_skipped_pois.extend(event_skipped)
        if adjusted_duration is not None:
            poi_id = _require_field(event_req.poi_id, "poi_id", event_req.type)
            duration_adjustments[poi_id] = adjusted_duration
    return ReplanningService.replan(
        itinerary=itinerary,
        availability_window=availability_window,
        current_time=effective_time,
        travel_time_minutes=travel_time_minutes,
        coordinates=current_coordinate,
        intercity_connection=intercity_connection,
        excluded_pois=[
            *excluded_pois,
            *event_closed_pois,
            *event_skipped_pois,
        ],
        reserved_future_stops=reserved_future_stops,
        reserved_meal_slots=reserved_meal_slots,
        duration_adjustments=duration_adjustments,
    )
