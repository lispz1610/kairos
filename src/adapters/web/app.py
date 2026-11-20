"""App web FastAPI (#38): endpoint ``POST /api/trip/replan`` e o Roteiro do Dia de Viagem."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.adapters.web.contingency import ContingencyEvent, apply_contingency_event
from src.core.domain.events import DurationAdjustmentEvent
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


class ReplanRequest(BaseModel):
    """Corpo de ``POST /api/trip/replan``: o Roteiro do Dia de Viagem antes dos Eventos e os Eventos aplicados."""

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
    events: list[ContingencyEvent] = Field(
        default_factory=list,
        description="Eventos de Contingência aplicados ao Roteiro do Dia de Viagem.",
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
    adjusted: tuple[str, int] | None = None
    for event in request.events:
        current_time, event_closed, event_skipped, new_duration = apply_contingency_event(
            day, current_time, event
        )
        closed_pois.extend(event_closed)
        skipped_pois.extend(event_skipped)
        if isinstance(event, DurationAdjustmentEvent) and new_duration is not None:
            adjusted = (event.poi_id, new_duration)
    if adjusted is not None:
        day = _with_adjusted_duration(day, adjusted[0], adjusted[1])
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
    )
    return ReplanResponse(
        itinerary=result.itinerary.stops,
        preserved_pois=result.preserved_pois,
        removed_pois=result.removed_pois,
        intercity_risk_alert=result.intercity_risk_alert,
    )


def _with_adjusted_duration(
    day: Itinerary, poi_id: str, duration_minutes: int
) -> Itinerary:
    """Roteiro com o Tempo de Permanência do POI ajustado — quando o POI está no Roteiro."""
    return Itinerary(
        stops=[
            RouteStop(poi=stop.poi, start=stop.start, duration_minutes=duration_minutes)
            if stop.poi.id == poi_id
            else stop
            for stop in day.stops
        ]
    )


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Roteiro do Dia de Viagem: linha do tempo do Dia ativo + mapa Leaflet."""
    template = Path(__file__).resolve().parent / "templates" / "index.html"
    return HTMLResponse(template.read_text(encoding="utf-8"))
