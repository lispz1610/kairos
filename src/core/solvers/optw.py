"""Motor OPTW do Roteiro Urbano (#36).

Heurística construtiva de inserção gulosa ponderada pela Pontuação de
Utilidade / Custo Marginal de Tempo (ADR 0001), seguida de busca local de
swaps de paradas e 2-opt: o problema modelado é a seleção e sequenciamento
de um subconjunto de Pontos de Interesse que maximiza a Pontuação de
Utilidade acumulada respeitando os Horários de Funcionamento dos POIs e a
Janela de Disponibilidade (ADR 0001).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta

from src.core.domain.models import POI, Itinerary, RouteStop, TimeWindow
from src.core.services.schedule import ScheduleService

__all__ = ["OPTWSolver"]

_VISIT_DURATION_MINUTES = 0
"""Tempo de Permanência do POI: o modelo ``POI`` não fornece Tempo de
Permanência configurado, então o visitante descansa 0 minutos no interior do
POI; o constraint de Janela de Funcionamento aplica ao horário da visita."""


class OPTWSolver:
    """Motor OPTW: gera um Roteiro de Pontos de Interesse dentro da
    Janela de Disponibilidade, maximizando a Pontuação de Utilidade
    acumulada."""

    @staticmethod
    def solve(
        candidate_pois: list[POI],
        availability_window: TimeWindow,
        travel_time_minutes: float,
        start_time: datetime | None = None,
        visit_durations: Mapping[str, int] | None = None,
    ) -> Itinerary:
        """Gera o Roteiro para a Janela de Disponibilidade.

        O Roteiro é construído por inserção gulosa — em cada ciclo escolhe-se
        o POI com maior Pontuação de Utilidade por Custo Marginal de Tempo
        em qualquer posição onde a inserção se mantém viável — seguido de
        busca local (swaps de paradas e 2-opt) que reduz o término do
        Roteiro mantendo-o viável.

        Args:
            candidate_pois: Pontos de Interesse candidatos à visita.
            availability_window: Janela de Disponibilidade do Dia de Viagem.
            travel_time_minutes: Custo de Deslocamento (Tempo de Trânsito)
                entre dois Pontos de Interesse consecutivos.
            start_time: Horário de início do Roteiro; quando omitido, o
                início é o horário de início da Janela de Disponibilidade.
            visit_durations: Tempo de Permanência ajustado por identificação
                do POI — usado em vez do Tempo de Permanência padrão em todas
                as simulações do Roteiro.

        Returns:
            O Roteiro construído: subconjunto e sequência de visitas aos
            Pontos de Interesse, em ordem cronológica, respeitando os
            Horários de Funcionamento dos POIs e a Janela de Disponibilidade.
        """
        if start_time is None:
            start_time = datetime.combine(date.today(), availability_window.start)
        route: list[POI] = []
        remaining = _unique_pois(candidate_pois)
        while True:
            inserted = _insert_pass(
                route,
                remaining,
                start_time,
                travel_time_minutes,
                availability_window,
                visit_durations,
            )
            moved = _local_search(
                route,
                start_time,
                travel_time_minutes,
                availability_window,
                visit_durations,
            )
            if inserted == 0 and moved == 0:
                break
        return _simulate(route, start_time, travel_time_minutes, visit_durations)


def _unique_pois(candidate_pois: list[POI]) -> list[POI]:
    """Remove duplicatas, pelo identificador do POI, mantendo a ordem."""
    seen: set[str] = set()
    unique: list[POI] = []
    for poi in candidate_pois:
        if poi.id not in seen:
            seen.add(poi.id)
            unique.append(poi)
    return unique


def _simulate(
    sequence: list[POI],
    start_time: datetime,
    travel_time_minutes: float,
    visit_durations: Mapping[str, int] | None = None,
) -> Itinerary:
    """Constrói o ``Itinerary``: ``RouteStop`` por POI com ``start``
    cronológico, descendo ``cursor`` do ``start_time`` pelo Custo de
    Deslocamento entre paradas — o Tempo de Permanência do POI é
    ``visit_durations.get(poi.id, _VISIT_DURATION_MINUTES)``."""
    durations: Mapping[str, int] = visit_durations or {}
    stops: list[RouteStop] = []
    cursor = start_time
    for poi in sequence:
        duration_minutes = durations.get(poi.id, _VISIT_DURATION_MINUTES)
        stops.append(
            RouteStop(poi=poi, start=cursor, duration_minutes=duration_minutes)
        )
        cursor = cursor + timedelta(minutes=duration_minutes + travel_time_minutes)
    return Itinerary(stops=stops)


def _is_feasible(
    sequence: list[POI],
    start_time: datetime,
    travel_time_minutes: float,
    availability_window: TimeWindow,
    visit_durations: Mapping[str, int] | None = None,
) -> bool:
    """Verdade quando o Roteiro da sequência não apresenta desvios: cada
    visita dentro do Horário de Funcionamento do POI e dentro da Janela de
    Disponibilidade, reportados por ``ScheduleService``."""
    itinerary = _simulate(sequence, start_time, travel_time_minutes, visit_durations)
    return ScheduleService.validate_itinerary(itinerary, availability_window) == []


def _completion(itinerary: Itinerary, start_time: datetime) -> datetime:
    """Momento em que o Roteiro termina: o fim da última visita (ou
    ``start_time`` quando o Roteiro está vazio)."""
    if not itinerary.stops:
        return start_time
    return itinerary.stops[-1].end


def _route_completion(
    sequence: list[POI],
    start_time: datetime,
    travel_time_minutes: float,
    visit_durations: Mapping[str, int] | None = None,
) -> datetime:
    """Momento em que o Roteiro da sequência termina: o fim da última visita
    (ou ``start_time`` quando o Roteiro está vazio)."""
    return _completion(
        _simulate(sequence, start_time, travel_time_minutes, visit_durations),
        start_time,
    )


def _weight(poi: POI, marginal_cost: float) -> float:
    """Valor ponderado da Pontuação de Utilidade do POI pelo Custo Marginal
    de Tempo de inserção; Custo Marginal nulo com Pontuação de Utilidade
    positiva configura valor infinito."""
    if marginal_cost <= 0:
        return float("inf") if poi.utility_score > 0 else 0.0
    return poi.utility_score / marginal_cost


def _insert_pass(
    route: list[POI],
    remaining: list[POI],
    start_time: datetime,
    travel_time_minutes: float,
    availability_window: TimeWindow,
    visit_durations: Mapping[str, int] | None = None,
) -> int:
    """Passo de inserção gulosa: em cada ciclo insere o POI com maior
    Pontuação de Utilidade por Custo Marginal de Tempo — em qualquer
    posição do Roteiro onde a inserção permanece viável — até que não haja
    inserção viável. Retorna o número de inserções realizadas."""
    inserted = 0
    while True:
        route_completion = _route_completion(
            route, start_time, travel_time_minutes, visit_durations
        )
        best_poi: POI | None = None
        best_position = -1
        best_weight = float("-inf")
        for poi in sorted(remaining, key=lambda candidate: candidate.id):
            if poi.utility_score <= 0:
                continue
            for position in range(len(route) + 1):
                candidate = route[:position] + [poi] + route[position:]
                if not _is_feasible(
                    candidate,
                    start_time,
                    travel_time_minutes,
                    availability_window,
                    visit_durations,
                ):
                    continue
                marginal_cost = (
                    _route_completion(
                        candidate, start_time, travel_time_minutes, visit_durations
                    )
                    - route_completion
                ).total_seconds() / 60
                weight = _weight(poi, marginal_cost)
                if weight > best_weight:
                    best_weight = weight
                    best_poi = poi
                    best_position = position
        if best_poi is None:
            return inserted
        route.insert(best_position, best_poi)
        remaining.remove(best_poi)
        inserted += 1


def _improving_completion(
    sequence: list[POI],
    start_time: datetime,
    travel_time_minutes: float,
    availability_window: TimeWindow,
    bound: datetime,
    visit_durations: Mapping[str, int] | None = None,
) -> datetime | None:
    """Retorna o término do Roteiro da sequência quando viável e
    estritamente anterior ao ``bound``; ``None`` caso contrário."""
    if not _is_feasible(
        sequence, start_time, travel_time_minutes, availability_window, visit_durations
    ):
        return None
    completion = _route_completion(
        sequence, start_time, travel_time_minutes, visit_durations
    )
    if completion >= bound:
        return None
    return completion


def _local_search(
    route: list[POI],
    start_time: datetime,
    travel_time_minutes: float,
    availability_window: TimeWindow,
    visit_durations: Mapping[str, int] | None = None,
) -> int:
    """Busca local: swaps de paradas e 2-opt sobre o Roteiro — a move é
    aceita quando o Roteiro permanece viável e seu término se antecipa,
    mantendo a Pontuação de Utilidade acumulada. A cada iteração aplica-se
    a move que antecipa mais o término. Retorna o número de moves
    aplicados até a ótima local."""
    moves = 0
    while True:
        current_completion = _route_completion(
            route, start_time, travel_time_minutes, visit_durations
        )
        best_route: list[POI] | None = None
        best_completion = current_completion
        for i in range(len(route)):
            for j in range(i + 1, len(route)):
                candidate = list(route)
                candidate[i], candidate[j] = candidate[j], candidate[i]
                completion = _improving_completion(
                    candidate,
                    start_time,
                    travel_time_minutes,
                    availability_window,
                    best_completion,
                    visit_durations,
                )
                if completion is not None:
                    best_completion = completion
                    best_route = candidate
        for i in range(len(route) - 1):
            for j in range(i + 1, len(route)):
                candidate = route[: i + 1] + route[i + 1: j + 1][::-1] + route[j + 1:]
                completion = _improving_completion(
                    candidate,
                    start_time,
                    travel_time_minutes,
                    availability_window,
                    best_completion,
                    visit_durations,
                )
                if completion is not None:
                    best_completion = completion
                    best_route = candidate
        if best_route is None:
            return moves
        route = best_route
        moves += 1
