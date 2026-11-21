"""App web FastAPI (#38): endpoint ``POST /api/trip/replan`` e o Roteiro do Dia de Viagem."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, model_validator

from src.adapters.web.contingency import ContingencyEvent, apply_contingency_event
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
    RouteStop,
    TimeWindow,
)
from src.core.services.replanning import (
    InterCityRiskAlert,
    ReplanningService,
    ReplanResult,
)

__all__ = ["ReplanRequest", "ReplanResponse", "app"]

DEFAULT_TRAVEL_TIME_MINUTES = 15.0
"""Custo de Deslocamento padrão entre Paradas do Roteiro, em minutos."""

app = FastAPI(title="Kairos — Dia de Viagem")


class ContingencyEventRequest(BaseModel):
    """Evento de Contingência ao Roteiro do Dia de Viagem — tipo explícito.

    O ``type`` declara o tipo do Evento e os campos restantes são obrigatórios
    por tipo — o ``model_validator`` rejeita Eventos incompletos — para que a
    validação do endpoint substitua a coerção implícita de uma união Pydantic
    (``ClosureEvent`` e ``SkipStopEvent`` têm formas idênticas).
    """

    type: Literal["delay", "closure", "skip", "duration_adjustment"] = Field(
        description="Tipo do Evento de Contingência: 'delay', 'closure', 'skip' ou 'duration_adjustment'."
    )
    poi_id: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Identificação do POI: fechado ('closure'), pulado ('skip') ou "
            "com Tempo de Permanência ajustado ('duration_adjustment')."
        ),
    )
    delay_minutes: int | None = Field(
        default=None,
        ge=0,
        description="Atraso em minutos a partir do horário atual ('delay').",
    )
    new_duration_minutes: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Novo Tempo de Permanência do POI, em minutos "
            "('duration_adjustment')."
        ),
    )

    @model_validator(mode="after")
    def _fields_required_by_type(self) -> ContingencyEventRequest:
        """Exige, por ``type``, os campos do Evento de Contingência:
        ``delay_minutes`` para 'delay'; ``poi_id`` para 'closure', 'skip' e
        'duration_adjustment'; ``new_duration_minutes`` para
        'duration_adjustment'."""
        if self.type == "delay":
            if self.delay_minutes is None:
                raise ValueError(
                    "delay_minutes é obrigatório para o Evento 'delay'."
                )
        elif self.type == "duration_adjustment":
            if self.poi_id is None:
                raise ValueError(
                    "poi_id é obrigatório para o Evento 'duration_adjustment'."
                )
            if self.new_duration_minutes is None:
                raise ValueError(
                    "new_duration_minutes é obrigatório para o Evento "
                    "'duration_adjustment'."
                )
        elif self.poi_id is None:
            raise ValueError(
                "poi_id é obrigatório para os Eventos 'closure' e 'skip'."
            )
        return self


class ReplanRequest(BaseModel):
    """Corpo de ``POST /api/trip/replan``: o Roteiro do Dia de Viagem antes dos
    Eventos de Contingência, os Eventos aplicados e as Paradas futuras
    reservadas que devem permanecer no Roteiro replanejado."""

    day_id: str = Field(min_length=1, description="Identificação do Dia de Viagem.")
    itinerary: Itinerary = Field(
        description="Roteiro do Dia de Viagem antes dos Eventos de Contingência."
    )
    current_time: datetime = Field(description="Horário atual do Dia de Viagem.")
    availability_window: TimeWindow = Field(
        description="Janela de Disponibilidade do Dia de Viagem."
    )
    current_coordinate: Coordinates = Field(
        description="Coordenada geográfica atual do visitante."
    )
    events: list[ContingencyEventRequest] = Field(
        default_factory=list,
        description="Eventos de Contingência aplicados ao Roteiro do Dia de Viagem.",
    )
    reserved_future_stops: list[RouteStop] = Field(
        default_factory=list,
        description=(
            "Paradas futuras já reservadas (Slots de Refeição) que devem ser "
            "preservadas no Roteiro replanejado."
        ),
    )
    closed_pois: list[str] = Field(
        default_factory=list,
        description="POIs já fechados — excluídos do Replanejamento.",
    )
    skipped_pois: list[str] = Field(
        default_factory=list,
        description="POIs já pulados — excluídos do Replanejamento.",
    )
    intercity_connection: InterCityConnection | None = Field(
        default=None,
        description="Conexão Interurbana de saída do último dia da Etapa, quando houver.",
    )
    travel_time_minutes: float = Field(
        default=DEFAULT_TRAVEL_TIME_MINUTES,
        description="Custo de Deslocamento entre Paradas do Roteiro, em minutos.",
    )


class ReplanResponse(BaseModel):
    """Resposta de ``POST /api/trip/replan``: Roteiro replanejado e metadados de impacto."""

    itinerary: list[RouteStop] = Field(description="Paradas do Roteiro replanejado.")
    preserved_pois: list[str] = Field(
        description=(
            "POIs preservados: histórico do Roteiro até o horário atual e Slots "
            "de Refeição já reservados."
        )
    )
    removed_pois: list[str] = Field(
        description="POIs removidos ou substituídos na janela restante."
    )
    intercity_risk_alert: InterCityRiskAlert | None = Field(
        description=(
            "Alerta de Risco da Conexão Interurbana, quando a janela restante "
            "não couber o embarque."
        )
    )


@app.post("/api/trip/replan", response_model=ReplanResponse)
def trip_replan(request: ReplanRequest) -> ReplanResponse:
    """Aplica os Eventos de Contingência ao Roteiro do Dia de Viagem e devolve o Roteiro replanejado com métricas de impacto."""
    day = request.itinerary
    current_time = request.current_time
    closed_pois: list[str] = []
    skipped_pois: list[str] = []
    duration_adjustments: dict[str, int] = {}
    for event_req in request.events:
        event = _to_domain_event(
            event_req, current_time, request.current_coordinate
        )
        current_time, event_closed, event_skipped, _ = apply_contingency_event(
            day, current_time, event
        )
        closed_pois.extend(event_closed)
        skipped_pois.extend(event_skipped)
        if isinstance(event, DurationAdjustmentEvent):
            duration_adjustments[event.poi_id] = event.new_duration_minutes
    result: ReplanResult = ReplanningService.replan(
        itinerary=day,
        availability_window=request.availability_window,
        current_time=current_time,
        travel_time_minutes=request.travel_time_minutes,
        coordinates=request.current_coordinate,
        intercity_connection=request.intercity_connection,
        excluded_pois=[
            *request.closed_pois,
            *closed_pois,
            *request.skipped_pois,
            *skipped_pois,
        ],
        reserved_future_stops=request.reserved_future_stops,
        duration_adjustments=duration_adjustments,
    )
    return ReplanResponse(
        itinerary=result.itinerary.stops,
        preserved_pois=result.preserved_pois,
        removed_pois=result.removed_pois,
        intercity_risk_alert=result.intercity_risk_alert,
    )


def _to_domain_event(
    event_req: ContingencyEventRequest,
    current_time: datetime,
    coordinates: Coordinates,
) -> ContingencyEvent:
    """Constrói o Evento de Contingência de domínio a partir do Evento da
    requisição (``ContingencyEventRequest``): ``DelayEvent`` com
    ``current_time``/``coordinates`` do pedido; ``ClosureEvent``,
    ``SkipStopEvent`` e ``DurationAdjustmentEvent`` com os campos do Evento.
    Os campos ``Optional`` são garantidos não ``None`` pelo
    ``model_validator`` de ``ContingencyEventRequest`` por tipo ``type``."""
    if event_req.type == "delay":
        return DelayEvent(
            delay_minutes=cast(int, event_req.delay_minutes),
            current_time=current_time,
            coordinates=coordinates,
        )
    if event_req.type == "closure":
        return ClosureEvent(poi_id=cast(str, event_req.poi_id))
    if event_req.type == "skip":
        return SkipStopEvent(poi_id=cast(str, event_req.poi_id))
    return DurationAdjustmentEvent(
        poi_id=cast(str, event_req.poi_id),
        new_duration_minutes=cast(int, event_req.new_duration_minutes),
    )


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Roteiro do Dia de Viagem: linha do tempo do Dia ativo + mapa Leaflet."""
    template = Path(__file__).resolve().parent / "templates" / "index.html"
    return HTMLResponse(template.read_text(encoding="utf-8"))
