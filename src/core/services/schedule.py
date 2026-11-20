"""Serviço de schedule: validação temporal do Roteiro (#34).

``ScheduleService.validate_itinerary`` cobre o contrato de #34: cada visita
planejada no Roteiro deve estar dentro do horário de funcionamento do POI e
dentro da Janela de Disponibilidade; violações são reportadas como desvios
descritivos (lista de strings).
"""

from __future__ import annotations

from datetime import datetime

from src.core.domain.models import Itinerary, RouteStop, TimeWindow

__all__ = ["ScheduleService"]


def _format_datetime(value: datetime) -> str:
    return value.strftime("%d/%m/%Y %H:%M")


class ScheduleService:
    """Valida o tempo de execução de um Roteiro em relação aos horários dos POIs."""

    @staticmethod
    def validate_itinerary(
        itinerary: Itinerary, availability_window: TimeWindow
    ) -> list[str]:
        """Valida cada visita do Roteiro contra o horário de funcionamento do
        POI e contra a Janela de Disponibilidade.

        Retorna a lista de desvios descritivos; lista vazia quando o Roteiro
        está dentro dos horários.
        """
        deviations: list[str] = []
        for stop in itinerary.stops:
            deviations.extend(ScheduleService._validate_visit(stop, availability_window))
        return deviations

    @staticmethod
    def _validate_visit(
        stop: RouteStop, availability_window: TimeWindow
    ) -> list[str]:
        poi = stop.poi
        visit_end = stop.end
        operating_window = poi.operating_window
        deviations: list[str] = []

        if stop.start.time() < operating_window.start:
            deviations.append(
                f"Visita ao POI {poi.id} ({poi.name}) iniciada em "
                f"{_format_datetime(stop.start)} antes do início do horário de "
                f"funcionamento do POI ({operating_window.start:%H:%M})."
            )
        if visit_end.time() > operating_window.end:
            deviations.append(
                f"Visita ao POI {poi.id} ({poi.name}) encerrada em "
                f"{_format_datetime(visit_end)} após o fechamento do horário de "
                f"funcionamento do POI ({operating_window.end:%H:%M})."
            )
        if stop.start.time() < availability_window.start:
            deviations.append(
                f"Visita ao POI {poi.id} ({poi.name}) iniciada em "
                f"{_format_datetime(stop.start)} antes do início da Janela de "
                f"Disponibilidade ({availability_window.start:%H:%M})."
            )
        if visit_end.time() > availability_window.end:
            deviations.append(
                f"Visita ao POI {poi.id} ({poi.name}) encerrada em "
                f"{_format_datetime(visit_end)} após o término da Janela de "
                f"Disponibilidade ({availability_window.end:%H:%M})."
            )
        return deviations
