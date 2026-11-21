"""Modelos temporais do Dia de Viagem: ``InterCityConnection`` e demais tipos.

Os modelos definem o modelo temporal do Dia de Viagem, conforme as decisões
arquiteturais do parent #18:

- ``TimeWindow``: intervalo contínuo (``start`` e ``end``) — usado tanto como
  Janela de Funcionamento quanto como Janela de Disponibilidade;
- ``POI``: Ponto de Interesse com coordenadas e horário de funcionamento;
- ``RouteStop``: visita a um POI no Roteiro, com ``start`` e Tempo de Permanência;
- ``Itinerary``: ``Roteiro`` — sequência cronológica de visitas;
- ``InterCityConnection``: ``Conexão Interurbana`` com partida obrigatória
  (``departure_datetime``) e Margem de Embarque por Modal de Transporte.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

from pydantic import BaseModel, Field, model_validator

Coordinates = tuple[float, float]
"""Coordenada geográfica (latitude, longitude)."""

__all__ = [
    "POI",
    "Coordinates",
    "InterCityConnection",
    "Itinerary",
    "RouteStop",
    "TimeWindow",
]


class TimeWindow(BaseModel):
    """Intervalo contínuo de horário, de ``start`` a ``end``.

    Usado tanto como Janela de Funcionamento (horário de abertura e fechamento
    de um Ponto de Interesse) quanto como Janela de Disponibilidade (horário em
    que o Roteiro de um Dia de Viagem pode ser executado).
    """

    start: time = Field(description="Horário de início do intervalo.")
    end: time = Field(description="Horário de término do intervalo.")

    @model_validator(mode="after")
    def _validate_interval(self) -> TimeWindow:
        """A Janela deve terminar no ou após seu início."""
        if self.start > self.end:
            raise ValueError("Janela de intervalo inválida: início após término.")
        return self


class POI(BaseModel):
    """Ponto de Interesse: local geográfico delimitado, com coordenadas e
    horário de funcionamento."""

    id: str = Field(min_length=1, description="Identificação do Ponto de Interesse.")
    name: str = Field(
        min_length=1, description="Nome de exibição do Ponto de Interesse."
    )
    coordinates: Coordinates = Field(
        description="Coordenada geográfica (latitude, longitude)."
    )
    operating_window: TimeWindow = Field(
        description="Janela de Funcionamento do Ponto de Interesse."
    )
    utility_score: float = Field(
        default=1.0,
        description="Pontuação de Utilidade do Ponto de Interesse.",
    )


class RouteStop(BaseModel):
    """Visita a um Ponto de Interesse: ``poi``, ``start`` e Tempo de Permanência."""

    poi: POI = Field(description="Ponto de Interesse visitado.")
    start: datetime = Field(description="Horário de início da visita ao POI.")
    duration_minutes: int = Field(
        ge=0, description="Tempo de Permanência no POI, em minutos."
    )

    @property
    def end(self) -> datetime:
        """Terceiro do visitante: ``start`` + Tempo de Permanência no POI."""
        return self.start + timedelta(minutes=self.duration_minutes)


class Itinerary(BaseModel):
    """Roteiro: sequência cronológica ordenada de visitas a Pontos de Interesse."""

    stops: list[RouteStop] = Field(
        description="Paradas do Roteiro, em ordem cronológica."
    )
    start_location: Coordinates | None = Field(
        default=None,
        description=(
            "Coordenada do início do Roteiro replanejado — a coordenada atual "
            "do visitante."
        ),
    )


DEFAULT_MODAL: str = "driving"
"""Modal de Transporte padrão para ``InterCityConnection``."""

DEFAULT_BOARDING_CUTOFF_MINUTES: int = 30
"""Margem de Embarque padrão, em minutos, para modais não listados abaixo."""

DEFAULT_BOARDING_CUTOFF_BY_MODAL: dict[str, int] = {
    "flying": 120,
    "driving": 30,
    "transit": 30,
}
"""Margem de Embarque padrão (minutos) por Modal de Transporte."""


class InterCityConnection(BaseModel):
    """Conexão Interurbana: transição de longa distância com partida obrigatória
    (``departure_datetime``) e Margem de Embarque (``boarding_cutoff_minutes``)
    por Modal de Transporte."""

    origin: str = Field(min_length=1, description="Origem da Conexão Interurbana.")
    destination: str = Field(
        min_length=1, description="Destino da Conexão Interurbana."
    )
    departure_datetime: datetime = Field(description="Partida com data e hora.")
    modal: str = Field(
        default=DEFAULT_MODAL,
        min_length=1,
        description="Modal de Transporte da Conexão Interurbana.",
    )
    boarding_cutoff_minutes: int = Field(
        ge=0,
        description=(
            "Margem de Embarque em minutos; o padrão do Modal de Transporte é "
            "aplicado quando não informado."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _apply_modal_default(cls, data: Any) -> Any:
        """Aplica o padrão de Margem de Embarque do Modal de Transporte quando
        ``boarding_cutoff_minutes`` não é informado; valor explícito é
        respeitado."""
        if isinstance(data, dict) and data.get("boarding_cutoff_minutes") is None:
            modal = data.get("modal") or DEFAULT_MODAL
            data = {
                **data,
                "boarding_cutoff_minutes": DEFAULT_BOARDING_CUTOFF_BY_MODAL.get(
                    modal, DEFAULT_BOARDING_CUTOFF_MINUTES
                ),
            }
        return data
