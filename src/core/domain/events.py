"""Eventos de contingência: ocorrências que invalidam a programação do Roteiro.

Cada evento tipado descreve o que aconteceu em tempo de execução para que o
Replanejamento possa recalcular a janela restante do Roteiro: ``DelayEvent``
(atraso em minutos a partir do horário e coordenada atuais), ``ClosureEvent``
(fechamento prematuro de um POI específico), ``SkipStopEvent`` (cancelamento
de parada de um POI planejado) e ``DurationAdjustmentEvent`` (ajuste do Tempo
de Permanência de um POI específico).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_serializer

from src.core.domain.models import Coordinates

__all__ = [
    "ClosureEvent",
    "DelayEvent",
    "DurationAdjustmentEvent",
    "SkipStopEvent",
]


class DelayEvent(BaseModel):
    """Atraso em minutos a partir do horário e da coordenada atuais."""

    delay_minutes: int = Field(
        ge=0, description="Atraso em minutos a partir do horário atual."
    )
    current_time: datetime = Field(
        description="Horário atual a partir do qual o atraso é medido."
    )
    coordinates: Coordinates = Field(
        description="Coordenada geográfica atual (latitude, longitude)."
    )

    @model_serializer(mode="wrap")
    def serialize_model(self, handler: Any) -> Any:
        data = handler(self)
        # Serialize coordinates as tuple
        if "coordinates" in data:
            coords = data["coordinates"]
            if isinstance(coords, dict) and "latitude" in coords and "longitude" in coords:
                data["coordinates"] = (coords["latitude"], coords["longitude"])
            elif hasattr(coords, "as_tuple"):
                data["coordinates"] = coords.as_tuple()
        return data


class ClosureEvent(BaseModel):
    """Fechamento prematuro ou repentino de um POI específico (excluído do replanejamento)."""

    poi_id: str = Field(min_length=1, description="Identificação do POI fechado.")


class SkipStopEvent(BaseModel):
    """Cancelamento ou suspensão de uma parada de um POI planejado."""

    poi_id: str = Field(
        min_length=1, description="Identificação do POI cuja parada será cancelada."
    )


class DurationAdjustmentEvent(BaseModel):
    """Alteração do Tempo de Permanência do POI atual ou futuro."""

    poi_id: str = Field(
        min_length=1,
        description="Identificação do POI com Tempo de Permanência ajustado.",
    )
    new_duration_minutes: int = Field(
        ge=0, description="Novo Tempo de Permanência, em minutos."
    )
