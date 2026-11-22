"""Motor de Replanejamento do Roteiro Restante do Dia de Viagem (#37).

``ReplanningService.replan`` preserva o histórico do Roteiro antes do horário
atual e reotimiza apenas a janela restante do Dia de Viagem —
``[horário efetivo pós-evento, fim da Janela de Disponibilidade]`` — via
``OPTWSolver`` a partir do horário e coordenada atuais, respeitando
Slots de Refeição futuros já reservados, excluindo POIs fechados/pulados e
aplicando a proteção do teto seguro da Conexão Interurbana.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, time, timedelta
from typing import Union

from pydantic import BaseModel, Field

from src.core.domain.models import (
    Coordinates,
    InterCityConnection,
    Itinerary,
    ItineraryStop,
    RouteStop,
    TimeWindow,
)
from src.core.solvers.optw import OPTWSolver

__all__ = ["InterCityRiskAlert", "ReplanResult", "ReplanningService"]

# Type alias for stops that can be either RouteStop or ItineraryStop
StopUnion = Union[RouteStop, ItineraryStop]


class InterCityRiskAlert(BaseModel):
    """Alerta de Risco de Conexão Interurbana.

    Déficit de tempo em minutos entre o horário efetivo de partida/embarque e o
    teto seguro da Conexão Interurbana no último dia da Etapa de Viagem.
    """

    deficit_minutes: int = Field(
        ge=0,
        description=(
            "Déficit em minutos entre o horário efetivo de partida/embarque e o "
            "teto seguro da Conexão Interurbana."
        ),
    )


class ReplanResult(BaseModel):
    """Resultado do Replanejamento do Roteiro restante do Dia de Viagem.

    Contém o Roteiro replanejado e metadados de impacto.
    """

    itinerary: Itinerary = Field(
        description="Roteiro replanejado do Dia de Viagem."
    )
    preserved_pois: list[str] = Field(
        description=(
            "Identificação dos POIs preservados: histórico do Roteiro até o "
            "horário atual e Slots de Refeição futuros já reservados."
        )
    )
    removed_pois: list[str] = Field(
        description=(
            "Identificação dos POIs removidos ou substituídos na janela restante."
        )
    )
    intercity_risk_alert: InterCityRiskAlert | None = Field(
        description=(
            "Alerta de Risco de Conexão Interurbana, quando o retorno/embarque "
            "não couber antes do limite operacional."
        )
    )


class ReplanningService:
    """Serviço de Replanejamento dinâmico do Roteiro restante do Dia de Viagem."""

    @staticmethod
    def replan(
        itinerary: Itinerary,
        availability_window: TimeWindow,
        current_time: datetime,
        travel_time_minutes: float,
        coordinates: Coordinates,
        intercity_connection: InterCityConnection | None = None,
        excluded_pois: Sequence[str] = (),
        reserved_future_stops: Sequence[StopUnion] = (),
        duration_adjustments: Mapping[str, int] | None = None,
    ) -> ReplanResult:
        """Reotimizar o Roteiro restante do Dia de Viagem.

        A reotimização ocorre a partir do horário e da coordenada atuais.
        POIs até ``current_time`` permanecem travadas como histórico do
        Roteiro; POIs futuras já reservadas
        (``reserved_future_stops``) permanecem preservadas no Roteiro
        replanejado; a janela restante — ``[horário efetivo pós-evento, fim da
        Janela de Disponibilidade]`` — é reotimizada via ``OPTWSolver`` a partir
        do horário efetivo, excluindo os POIs fechados/pulados
        (``excluded_pois``) e aplicando o teto seguro da Conexão Interurbana
        quando o Dia de Viagem replanejado é o último dia da Etapa de Viagem
        com partida interurbana. O Roteiro replanejado permanece cronológico,
        mesmo quando o solver agenda POIs antes de Slots de Refeição futuros
        reservados.

        Args:
            itinerary: Roteiro do Dia de Viagem antes do evento de contingência.
            availability_window: Janela de Disponibilidade do Dia de Viagem.
            current_time: Horário atual a partir do qual o Roteiro é replanejado.
            travel_time_minutes: Custo de Deslocamento entre Pontos de Interesse
                consecutivos.
            coordinates: Coordenada atual do visitante — referência geográfica
                do Roteiro replanejado.
            intercity_connection: Conexão Interurbana de saída do último dia da
                Etapa de Viagem, quando houver.
            excluded_pois: Identificação dos POIs fechados/pulados pelo Evento de
                Contingência (``ClosureEvent``/``SkipStopEvent``).
            reserved_future_stops: POIs futuras já reservadas (Slots de
                Refeição), preservadas no Roteiro replanejado.
            duration_adjustments: Tempo de Permanência ajustado por identificação
                do POI (``DurationAdjustmentEvent``) — aplicado aos POIs
                preservadas e reservadas e passado ao ``OPTWSolver``
                (``visit_durations``), de modo que POIs agendadas pelo
                solver usam o Tempo de Permanência ajustado.

        Returns:
            O Roteiro replanejado e os metadados de impacto: POIs preservados,
            POIs removidos/substituídos e Alerta de Risco de Conexão Interurbana,
            quando o retorno/embarque não couber antes do limite operacional.
        """
        preserved: list[StopUnion] = ReplanningService._preserved_stops(itinerary, current_time)
        reserved: list[StopUnion] = list(reserved_future_stops)
        if duration_adjustments:
            preserved = ReplanningService._with_adjusted_durations(
                preserved, duration_adjustments
            )
            reserved = ReplanningService._with_adjusted_durations(
                reserved, duration_adjustments
            )
        prefix: list[StopUnion] = sorted(preserved + reserved, key=lambda stop: stop.start)
        prefix_ids = {stop.poi.id for stop in prefix}

        replan_start = ReplanningService._replan_start(
            prefix, current_time, availability_window
        )
        window_end = ReplanningService._window_end(
            availability_window, intercity_connection
        )
        alert = ReplanningService._intercity_alert(
            intercity_connection, window_end, replan_start
        )

        solver_route = Itinerary(stops=[])
        if ReplanningService._can_solve(
            alert, replan_start, availability_window, intercity_connection
        ):
            excluded_ids = set(excluded_pois)
            candidates = [
                stop.poi
                for stop in itinerary.stops
                if stop.poi.id not in prefix_ids and stop.poi.id not in excluded_ids
            ]
            solver_window = TimeWindow(start_time=availability_window.start, end_time=window_end)
            solver_route = OPTWSolver.replan_remaining(
                candidates,
                solver_window,
                travel_time_minutes,
                start_time=replan_start,
                visit_durations=duration_adjustments,
                start_location=coordinates,
            )

        # Roteiro replanado em ordem cronológica: o solver pode agendar POIs
        # antes de Slots de Refeição futuros reservados, e o Roteiro permanece
        # ordenado por horário de início.
        final_stops = sorted(prefix + solver_route.stops, key=lambda stop: stop.start)
        final_ids = {stop.poi.id for stop in final_stops}
        removed_pois = [
            stop.poi.id for stop in itinerary.stops if stop.poi.id not in final_ids
        ]
        return ReplanResult(
            itinerary=Itinerary(stops=final_stops, start_location=coordinates),
            preserved_pois=[stop.poi.id for stop in prefix],
            removed_pois=removed_pois,
            intercity_risk_alert=alert,
        )

    @staticmethod
    def _with_adjusted_durations(
        stops: Sequence[StopUnion], duration_adjustments: Mapping[str, int]
    ) -> list[StopUnion]:
        """Ajustar tempo de permanência das paradas.

        POIs com o Tempo de Permanência ajustado quando há ajuste para o
        POI (``duration_adjustments``); POIs sem ajuste inalteradas.
        """
        return [
            RouteStop(
                poi=stop.poi,
                start=stop.start,
                duration_minutes=duration_adjustments[stop.poi.id],
            )
            if stop.poi.id in duration_adjustments
            else stop
            for stop in stops
        ]

    @staticmethod
    def _preserved_stops(itinerary: Itinerary, current_time: datetime) -> list[StopUnion]:
        """Obter paradas preservadas até o horário atual.

        POIs até o ``current_time`` — já iniciadas pelo menos: preservadas
        como histórico do Roteiro, sem alteração.
        """
        return [
            stop
            for stop in itinerary.stops
            if (
                stop.start
                if isinstance(stop.start, datetime)
                else datetime.combine(current_time.date(), stop.start)
            )
            <= current_time
        ]

    @staticmethod
    def _replan_start(
        prefix: list[StopUnion], effective_start: datetime, availability_window: TimeWindow
    ) -> datetime:
        """Calcular horário de início da janela restante.

        O horário efetivo pós-evento adiantado pelos términos dos POIs preservados
        que já iniciaram antes do horário atual — POIs futuros já reservados não
        afastam o início da janela — nunca antes do início da Janela de Disponibilidade.
        """
        replan_start = effective_start
        for stop in prefix:
            start_time = (
                stop.start
                if isinstance(stop.start, datetime)
                else datetime.combine(replan_start.date(), stop.start)
            )
            if start_time <= replan_start:
                stop_end = stop.end
                if isinstance(stop_end, time):
                    stop_end = datetime.combine(replan_start.date(), stop_end)
                if stop_end > replan_start:
                    replan_start = stop_end
        if replan_start.time() < availability_window.start:
            replan_start = datetime.combine(
                replan_start.date(), availability_window.start
            )
        return replan_start

    @staticmethod
    def _window_end(
        availability_window: TimeWindow,
        intercity_connection: InterCityConnection | None,
    ) -> time:
        """Determinar teto do quadro replanejado.

        O fim da Janela de Disponibilidade, ou o limite operacional da Conexão
        Interurbana quando há embarque interurbano — ``min(availability_window.end_time,
        departure_datetime - boarding_cutoff_minutes)``.
        """
        if intercity_connection is None:
            return availability_window.end
        boarding_limit = (
            intercity_connection.departure_datetime
            - timedelta(minutes=intercity_connection.boarding_cutoff_minutes)
        ).time()
        return min(availability_window.end, boarding_limit)

    @staticmethod
    def _intercity_alert(
        intercity_connection: InterCityConnection | None,
        window_end: time,
        replan_start: datetime,
    ) -> InterCityRiskAlert | None:
        """Emitir alerta de risco de conexão interurbana se necessário.

        Alerta de Risco de Conexão Interurbana quando nem o embarque cai
        antes do teto seguro: déficit em minutos entre o horário efetivo de
        partida/embarque e o teto.
        """
        if intercity_connection is None or replan_start.time() <= window_end:
            return None
        limit = datetime.combine(replan_start.date(), window_end)
        deficit_minutes = int((replan_start - limit).total_seconds() // 60)
        return InterCityRiskAlert(deficit_minutes=deficit_minutes)

    @staticmethod
    def _can_solve(
        alert: InterCityRiskAlert | None,
        replan_start: datetime,
        availability_window: TimeWindow,
        intercity_connection: InterCityConnection | None,
    ) -> bool:
        """Verificar se o OPTWSolver pode gerar a janela restante.

        Verdade quando não há Alerta de Risco e o quadro replanejado é viável
        dentro da Janela de Disponibilidade.
        """
        window_end = ReplanningService._window_end(
            availability_window, intercity_connection
        )
        return (
            alert is None
            and availability_window.start <= window_end
            and replan_start.time() <= window_end
        )
