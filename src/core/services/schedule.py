from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import List

from pydantic import BaseModel

from src.core.domain.models import (
    POI,
    InterCityConnection,
    Itinerary,
    ItineraryStop,
    RouteStop,
    TimeWindow,
    Trip,
    TripDay,
    TripStage,
)


class ShiftedStageInfo(BaseModel):
    """Etapa de Viagem realocada com datas antigas, novas e quantidade de dias preservada."""

    stage_id: str
    city_name: str
    old_start: date
    old_end: date
    new_start: date
    new_end: date
    preserved_days_count: int


class ShiftedConnectionInfo(BaseModel):
    """Conexão Interurbana com a data de partida deslocada pelo Deslocamento em Cascata."""

    connection_id: str
    old_departure: date
    new_departure: date


class RippleShiftPreview(BaseModel):
    """Prévia do Deslocamento em Cascata com Etapas de Viagem e Conexões Interurbanas afetadas."""

    target_stage_id: str
    delta_days: int
    old_target_end: date
    new_target_end: date
    shifted_stages: List[ShiftedStageInfo]
    shifted_connections: List[ShiftedConnectionInfo]


class ScheduleService:
    """Gerencia a integridade temporal de jornadas multicidades com Deslocamento em Cascata."""

    def _find_stage_index(self, trip: Trip, target_stage_id: str) -> int:
        """Localiza o índice de uma etapa na viagem pelo seu identificador único."""
        for idx, stage in enumerate(trip.stages):
            if stage.id == target_stage_id:
                return idx
        raise ValueError(f"Etapa com ID '{target_stage_id}' não encontrada na viagem.")

    def preview_ripple_shift(
        self, trip: Trip, target_stage_id: str, delta_days: int
    ) -> RippleShiftPreview:
        """Calcula e retorna a prévia do impacto temporal do deslocamento em cascata."""
        stage_idx = self._find_stage_index(trip, target_stage_id)

        target_stage = trip.stages[stage_idx]
        new_target_end = target_stage.end_date + timedelta(days=delta_days)

        shifted_stages: List[ShiftedStageInfo] = []
        shifted_conns: List[ShiftedConnectionInfo] = []
        shift_delta = timedelta(days=delta_days)

        for i in range(stage_idx + 1, len(trip.stages)):
            st = trip.stages[i]
            shifted_stages.append(
                ShiftedStageInfo(
                    stage_id=st.id,
                    city_name=st.city_name,
                    old_start=st.start_date,
                    old_end=st.end_date,
                    new_start=st.start_date + shift_delta,
                    new_end=st.end_date + shift_delta,
                    preserved_days_count=len(st.days),
                )
            )

        for conn in trip.connections:
            if conn.effective_departure_time >= target_stage.end_date:
                shifted_conns.append(
                    ShiftedConnectionInfo(
                        connection_id=conn.id,
                        old_departure=conn.effective_departure_time,
                        new_departure=conn.effective_departure_time + shift_delta,
                    )
                )

        return RippleShiftPreview(
            target_stage_id=target_stage_id,
            delta_days=delta_days,
            old_target_end=target_stage.end_date,
            new_target_end=new_target_end,
            shifted_stages=shifted_stages,
            shifted_connections=shifted_conns,
        )

    def apply_ripple_shift(
        self, trip: Trip, target_stage_id: str, delta_days: int
    ) -> Trip:
        """Aplica o deslocamento em cascata à etapa informada e propaga para as seguintes."""
        if delta_days == 0:
            return trip

        stage_idx = self._find_stage_index(trip, target_stage_id)

        target_stage = trip.stages[stage_idx]
        new_end = target_stage.end_date + timedelta(days=delta_days)
        if new_end <= target_stage.start_date:
            raise ValueError("Uma etapa de viagem deve possuir no mínimo 1 dia de estadia.")

        shift_delta = timedelta(days=delta_days)
        if delta_days > 0:
            self._expand_stage_days(target_stage, delta_days)
        else:
            self._shrink_stage_days(target_stage, abs(delta_days))

        target_stage.end_date = new_end
        self._shift_subsequent_stages(trip.stages, stage_idx + 1, shift_delta)
        self._shift_connections(trip.connections, target_stage.end_date - shift_delta, shift_delta)

        return trip

    def _expand_stage_days(self, stage: TripStage, delta_days: int) -> None:
        current_last_date = stage.days[-1].date if stage.days else stage.start_date
        for i in range(delta_days):
            new_date = current_last_date + timedelta(days=i + 1)
            prev_acc = (
                stage.days[-1].effective_accommodation
                if stage.days
                else stage.base_accommodation
            )
            stage.days.append(
                TripDay(
                    date=new_date,
                    base_accommodation=stage.base_accommodation,
                    previous_day_accommodation=prev_acc,
                )
            )

    def _shrink_stage_days(self, stage: TripStage, remove_count: int) -> None:
        stage.days = stage.days[:-remove_count]

    def _shift_subsequent_stages(
        self, stages: List[TripStage], start_idx: int, shift_delta: timedelta
    ) -> None:
        for i in range(start_idx, len(stages)):
            st = stages[i]
            st.start_date += shift_delta
            st.end_date += shift_delta
            for day in st.days:
                day.date += shift_delta

    def _shift_connections(
        self, connections: List[InterCityConnection], threshold_date: date, shift_delta: timedelta
    ) -> None:
        for conn in connections:
            if conn.effective_departure_time >= threshold_date:
                # Update both departure_time and departure_datetime
                new_departure_time = conn.effective_departure_time + shift_delta
                conn.departure_time = new_departure_time
                conn.departure_datetime = datetime.combine(
                    new_departure_time, conn.departure_datetime.time()
                )

    @staticmethod
    def _normalize_stop_window(
        stop: RouteStop | ItineraryStop,
    ) -> tuple[datetime, datetime] | None:
        """Normaliza início e término de uma parada para datetime."""
        if not isinstance(stop, RouteStop):
            return None
        raw_start: datetime | time = stop.start
        if isinstance(raw_start, datetime):
            start_datetime = raw_start
        else:
            start_datetime = datetime.combine(date.today(), raw_start)
        visit_end = start_datetime + timedelta(minutes=stop.duration_minutes)
        return (start_datetime, visit_end)

    @staticmethod
    def _validate_stop_against_windows(
        poi: POI,
        start_datetime: datetime,
        visit_end: datetime,
        availability_window: TimeWindow,
    ) -> list[str]:
        """Verifica os quatro limites das janelas de funcionamento e disponibilidade."""
        start_time = start_datetime.time()
        visit_end_time = visit_end.time()
        deviations: list[str] = []
        for window, label, end_noun in (
            (poi.operating_window, "do horário de funcionamento do POI", "fechamento"),
            (availability_window, "da Janela de Disponibilidade", "término"),
        ):
            if start_time < window.start:
                deviations.append(
                    f"Visita ao POI {poi.id} ({poi.name}) iniciada em "
                    f"{start_datetime:%d/%m/%Y %H:%M} antes do início {label} "
                    f"({window.start:%H:%M})."
                )
            if visit_end_time > window.end:
                deviations.append(
                    f"Visita ao POI {poi.id} ({poi.name}) encerrada em "
                    f"{visit_end:%d/%m/%Y %H:%M} após o {end_noun} {label} "
                    f"({window.end:%H:%M})."
                )
        return deviations

    @staticmethod
    def validate_itinerary(
        itinerary: Itinerary, availability_window: TimeWindow
    ) -> list[str]:
        """Valida visitas no formato legado de contingência."""
        deviations: list[str] = []
        for stop in itinerary.stops:
            normalized = ScheduleService._normalize_stop_window(stop)
            if normalized is None:
                continue
            start_datetime, visit_end = normalized
            deviations.extend(
                ScheduleService._validate_stop_against_windows(
                    stop.poi,
                    start_datetime,
                    visit_end,
                    availability_window,
                )
            )
        return deviations
