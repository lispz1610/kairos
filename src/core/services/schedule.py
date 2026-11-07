from __future__ import annotations

from datetime import date, timedelta
from typing import List

from pydantic import BaseModel

from src.core.domain.models import InterCityConnection, Trip, TripDay, TripStage


class ShiftedStageInfo(BaseModel):
    stage_id: str
    city_name: str
    old_start: date
    old_end: date
    new_start: date
    new_end: date
    preserved_days_count: int


class ShiftedConnectionInfo(BaseModel):
    connection_id: str
    old_departure: date
    new_departure: date


class RippleShiftPreview(BaseModel):
    target_stage_id: str
    delta_days: int
    old_target_end: date
    new_target_end: date
    shifted_stages: List[ShiftedStageInfo]
    shifted_connections: List[ShiftedConnectionInfo]


class ScheduleService:
    """Gerencia a integridade temporal de jornadas multicidades com Deslocamento em Cascata."""

    def preview_ripple_shift(
        self, trip: Trip, target_stage_id: str, delta_days: int
    ) -> RippleShiftPreview:
        stage_idx = next(
            (i for i, st in enumerate(trip.stages) if st.id == target_stage_id), -1
        )
        if stage_idx == -1:
            raise ValueError(f"Etapa com ID '{target_stage_id}' não encontrada na viagem.")

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
            if conn.departure_time >= target_stage.end_date:
                shifted_conns.append(
                    ShiftedConnectionInfo(
                        connection_id=conn.id,
                        old_departure=conn.departure_time,
                        new_departure=conn.departure_time + shift_delta,
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
        if delta_days == 0:
            return trip

        stage_idx = next(
            (i for i, st in enumerate(trip.stages) if st.id == target_stage_id), -1
        )
        if stage_idx == -1:
            raise ValueError(f"Etapa com ID '{target_stage_id}' não encontrada.")

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
            if conn.departure_time >= threshold_date:
                conn.departure_time += shift_delta
