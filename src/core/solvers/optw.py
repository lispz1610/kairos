"""Motor OPTW do Roteiro Urbano (#36) e Solver Heurístico com Janelas Temporais."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple

from src.core.domain.models import (
    POI,
    Coordinates,
    Itinerary,
    ItineraryStop,
    PreferencesProfile,
    RouteStop,
    TimeWindow,
)
from src.core.services.schedule import ScheduleService

__all__ = ["OPTWSolver", "haversine_distance_km", "estimate_transit_minutes"]


def haversine_distance_km(coord1: Coordinates, coord2: Coordinates) -> float:
    """Calcula a distância ortodrômica entre duas coordenadas geográficas em quilômetros."""
    r = 6371.0
    phi1 = math.radians(coord1.latitude)
    phi2 = math.radians(coord2.latitude)
    delta_phi = math.radians(coord2.latitude - coord1.latitude)
    delta_lambda = math.radians(coord2.longitude - coord1.longitude)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def estimate_transit_minutes(
    coord1: Coordinates, coord2: Coordinates, speed_kmh: float = 25.0
) -> int:
    """Estima o tempo de deslocamento em minutos considerando velocidade média urbana."""
    dist = haversine_distance_km(coord1, coord2)
    minutes = int(math.ceil((dist / speed_kmh) * 60.0))
    return max(2, minutes)


def minutes_to_time(minutes_since_midnight: int) -> time:
    """Calcular o objeto time correspondente aos minutos decorridos desde a meia-noite."""
    normalized = minutes_since_midnight % (24 * 60)
    hours = normalized // 60
    minutes = normalized % 60
    return time(hour=hours, minute=minutes)


def time_to_minutes(t: time) -> int:
    """Calcular os minutos decorridos desde a meia-noite a partir de um objeto time."""
    return t.hour * 60 + t.minute


@dataclass(frozen=True)
class FeasibilityContext:
    """Parâmetros de contorno e restrições temporais para avaliação de viabilidade."""

    end_location: Coordinates
    window_end_min: int
    reserved_ranges: List[Tuple[int, int]]


@dataclass(frozen=True)
class CandidateSchedule:
    """Horários calculados para visitação de um POI."""

    arrival_min: int
    departure_min: int
    transit_min: int


class OPTWSolver:
    """Solver heurístico com busca local para Orienteering Problem with Time Windows (OPTW).

    Maximiza utilidade acumulada respeitando horários de funcionamento,
    janela diária e slots reservados para refeições e pausas temáticas.
    """

    def __init__(self, transit_speed_kmh: float = 25.0) -> None:
        """Inicializar o solver com a velocidade média usada nos Deslocamentos urbanos."""
        self.transit_speed_kmh = transit_speed_kmh

    def solve(
        self,
        start_location: Coordinates,
        end_location: Coordinates,
        window: TimeWindow,
        candidates: List[POI],
        preferences: Optional[PreferencesProfile] = None,
        reserved_slots: Optional[List[TimeWindow]] = None,
    ) -> Itinerary:
        """Planejar o Roteiro diário respeitando restrições temporais e slots reservados."""
        if not candidates:
            return Itinerary(stops=[], total_utility=0.0, total_duration_minutes=0)

        effective_candidates = self._prepare_candidates(candidates, preferences)
        reserved_ranges = self._convert_reserved_slots(reserved_slots)
        window_start_min = time_to_minutes(window.start_time)
        window_end_min = time_to_minutes(window.end_time)

        context = FeasibilityContext(
            end_location=end_location,
            window_end_min=window_end_min,
            reserved_ranges=reserved_ranges,
        )

        initial_itinerary, remaining = self._build_greedy_solution(
            start_location=start_location,
            window_start_min=window_start_min,
            candidates=effective_candidates,
            context=context,
        )

        if not initial_itinerary.stops:
            return initial_itinerary

        return self._local_search(
            initial_itinerary=initial_itinerary,
            remaining_candidates=remaining,
            start_location=start_location,
            window_start_min=window_start_min,
            context=context,
        )

    @staticmethod
    def replan_remaining(
        candidate_pois: list[POI],
        availability_window: TimeWindow,
        travel_time_minutes: float = 15.0,
        start_time: datetime | None = None,
        visit_durations: Mapping[str, int] | None = None,
        start_location: Coordinates | None = None,
    ) -> Itinerary:
        """Executar o Replanejamento do Roteiro restante após um Evento de Contingência."""
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
            moved = _local_search_contingency(
                route,
                start_time,
                travel_time_minutes,
                availability_window,
                visit_durations,
            )
            if inserted == 0 and moved == 0:
                break
        return _simulate(
            route, start_time, travel_time_minutes, visit_durations, start_location
        )

    def _prepare_candidates(
        self, candidates: List[POI], preferences: Optional[PreferencesProfile]
    ) -> List[POI]:
        if preferences is not None:
            from src.core.services.preferences import PreferencesService

            return PreferencesService().apply_preference_weights(candidates, preferences)
        return candidates

    def _convert_reserved_slots(
        self, reserved_slots: Optional[List[TimeWindow]]
    ) -> List[Tuple[int, int]]:
        if not reserved_slots:
            return []
        ranges = [
            (time_to_minutes(s.start_time), time_to_minutes(s.end_time))
            for s in reserved_slots
        ]
        return sorted(ranges, key=lambda r: r[0])

    def _skip_reserved_slots(
        self, current_time_min: int, reserved_ranges: List[Tuple[int, int]]
    ) -> int:
        t = current_time_min
        for r_start, r_end in reserved_ranges:
            if r_start <= t < r_end:
                t = r_end
        return t

    def _find_overlapping_slot(
        self, start_min: int, end_min: int, reserved_ranges: List[Tuple[int, int]]
    ) -> Optional[Tuple[int, int]]:
        for r_start, r_end in reserved_ranges:
            if max(start_min, r_start) < min(end_min, r_end):
                return (r_start, r_end)
        return None

    def _is_feasible_route(
        self,
        schedule: CandidateSchedule,
        poi: POI,
        context: FeasibilityContext,
    ) -> bool:
        poi_close = time_to_minutes(poi.window.end_time)
        if schedule.departure_min > poi_close:
            return False

        ret_transit = estimate_transit_minutes(
            poi.location, context.end_location, self.transit_speed_kmh
        )
        if schedule.departure_min + ret_transit > context.window_end_min:
            return False

        for r_start, r_end in context.reserved_ranges:
            if max(schedule.arrival_min, r_start) < min(schedule.departure_min, r_end):
                return False

        return True

    def _compute_schedule(
        self,
        poi: POI,
        current_location: Coordinates,
        current_time_min: int,
        context: FeasibilityContext,
    ) -> Optional[CandidateSchedule]:
        t = current_time_min
        max_attempts = len(context.reserved_ranges) + 1

        for _ in range(max_attempts):
            t = self._skip_reserved_slots(t, context.reserved_ranges)
            transit_min = estimate_transit_minutes(
                current_location, poi.location, self.transit_speed_kmh
            )
            arr_min = t + transit_min
            poi_open = time_to_minutes(poi.window.start_time)
            service_start_min = max(arr_min, poi_open)
            dep_min = service_start_min + poi.stay_duration_minutes

            overlap = self._find_overlapping_slot(
                arr_min, dep_min, context.reserved_ranges
            )
            if overlap is not None:
                _, r_end = overlap
                t = r_end
                continue

            sched = CandidateSchedule(
                arrival_min=arr_min,
                departure_min=dep_min,
                transit_min=transit_min,
            )
            if self._is_feasible_route(sched, poi, context):
                return sched
            return None

        return None

    def _calculate_candidate_score(self, poi: POI, sched: CandidateSchedule) -> float:
        poi_open = time_to_minutes(poi.window.start_time)
        wait_min = max(0, poi_open - sched.arrival_min)
        total_time = float(sched.transit_min + poi.stay_duration_minutes + wait_min)
        return poi.utility_score / max(1.0, total_time)

    def _find_best_candidate(
        self,
        current_location: Coordinates,
        current_time_min: int,
        candidates: List[POI],
        context: FeasibilityContext,
    ) -> Optional[Tuple[POI, CandidateSchedule]]:
        best_candidate: Optional[POI] = None
        best_schedule: Optional[CandidateSchedule] = None
        best_score = -1.0

        for poi in candidates:
            sched = self._compute_schedule(
                poi=poi,
                current_location=current_location,
                current_time_min=current_time_min,
                context=context,
            )
            if sched is None:
                continue

            score = self._calculate_candidate_score(poi, sched)
            if score > best_score:
                best_score = score
                best_candidate = poi
                best_schedule = sched

        if best_candidate is None or best_schedule is None:
            return None
        return (best_candidate, best_schedule)

    def _build_greedy_solution(
        self,
        start_location: Coordinates,
        window_start_min: int,
        candidates: List[POI],
        context: FeasibilityContext,
    ) -> Tuple[Itinerary, List[POI]]:
        current_location = start_location
        current_time_min = window_start_min
        remaining = list(candidates)
        selected_stops: List[ItineraryStop] = []
        total_utility = 0.0

        while remaining:
            best = self._find_best_candidate(
                current_location=current_location,
                current_time_min=current_time_min,
                candidates=remaining,
                context=context,
            )
            if best is None:
                break

            poi, sched = best
            selected_stops.append(
                ItineraryStop(
                    poi=poi,
                    arrival_time=minutes_to_time(sched.arrival_min),
                    departure_time=minutes_to_time(sched.departure_min),
                    transit_duration_minutes=sched.transit_min,
                )
            )
            total_utility += poi.utility_score
            current_location = poi.location
            current_time_min = sched.departure_min
            remaining.remove(poi)

        final_transit = (
            estimate_transit_minutes(
                current_location, context.end_location, self.transit_speed_kmh
            )
            if selected_stops
            else 0
        )
        total_duration = (current_time_min + final_transit) - window_start_min

        initial_itinerary = Itinerary(
            stops=selected_stops,
            total_utility=total_utility,
            total_duration_minutes=max(0, total_duration),
        )
        return initial_itinerary, remaining

    def _evaluate_route(
        self,
        pois: List[POI],
        start_location: Coordinates,
        window_start_min: int,
        context: FeasibilityContext,
    ) -> Optional[Itinerary]:
        if not pois:
            return Itinerary(stops=[], total_utility=0.0, total_duration_minutes=0)

        current_location = start_location
        current_time_min = window_start_min
        stops: List[ItineraryStop] = []
        total_utility = 0.0

        for poi in pois:
            sched = self._compute_schedule(
                poi, current_location, current_time_min, context
            )
            if sched is None:
                return None

            stops.append(
                ItineraryStop(
                    poi=poi,
                    arrival_time=minutes_to_time(sched.arrival_min),
                    departure_time=minutes_to_time(sched.departure_min),
                    transit_duration_minutes=sched.transit_min,
                )
            )
            total_utility += poi.utility_score
            current_location = poi.location
            current_time_min = sched.departure_min

        final_transit = estimate_transit_minutes(
            current_location, context.end_location, self.transit_speed_kmh
        )
        if current_time_min + final_transit > context.window_end_min:
            return None

        total_duration = (current_time_min + final_transit) - window_start_min
        return Itinerary(
            stops=stops,
            total_utility=total_utility,
            total_duration_minutes=max(0, total_duration),
        )

    def _is_better(self, candidate: Itinerary, current: Itinerary) -> bool:
        if candidate.total_utility > current.total_utility + 1e-6:
            return True
        if abs(candidate.total_utility - current.total_utility) > 1e-6:
            return False
        cand_transit = sum(
            s.transit_duration_minutes
            for s in candidate.stops
            if isinstance(s, ItineraryStop)
        )
        curr_transit = sum(
            s.transit_duration_minutes
            for s in current.stops
            if isinstance(s, ItineraryStop)
        )
        if cand_transit < curr_transit:
            return True
        return (
            cand_transit == curr_transit
            and candidate.total_duration_minutes < current.total_duration_minutes
        )

    def _try_2opt_improvement(
        self,
        current_pois: List[POI],
        start_location: Coordinates,
        window_start_min: int,
        context: FeasibilityContext,
        best_itinerary: Itinerary,
    ) -> Optional[Itinerary]:
        n = len(current_pois)
        if n < 3:
            return None
        for i in range(n - 1):
            for j in range(i + 1, n):
                if i == 0 and j == n - 1:
                    continue
                candidate_pois = (
                    current_pois[:i]
                    + list(reversed(current_pois[i : j + 1]))
                    + current_pois[j + 1 :]
                )
                cand_itinerary = self._evaluate_route(
                    candidate_pois, start_location, window_start_min, context
                )
                if cand_itinerary and self._is_better(cand_itinerary, best_itinerary):
                    return cand_itinerary
        return None

    def _try_swap_improvement(
        self,
        current_pois: List[POI],
        start_location: Coordinates,
        window_start_min: int,
        context: FeasibilityContext,
        best_itinerary: Itinerary,
    ) -> Optional[Itinerary]:
        n = len(current_pois)
        if n < 2:
            return None
        for i in range(n - 1):
            for j in range(i + 1, n):
                candidate_pois = list(current_pois)
                candidate_pois[i], candidate_pois[j] = candidate_pois[j], candidate_pois[i]
                cand_itinerary = self._evaluate_route(
                    candidate_pois, start_location, window_start_min, context
                )
                if cand_itinerary and self._is_better(cand_itinerary, best_itinerary):
                    return cand_itinerary
        return None

    def _try_candidate_swap(
        self,
        current_pois: List[POI],
        unvisited: List[POI],
        start_location: Coordinates,
        window_start_min: int,
        context: FeasibilityContext,
        best_itinerary: Itinerary,
    ) -> Tuple[Optional[Itinerary], List[POI]]:
        for i in range(len(current_pois)):
            for cand in unvisited:
                candidate_pois = list(current_pois)
                old_poi = candidate_pois[i]
                candidate_pois[i] = cand
                cand_itinerary = self._evaluate_route(
                    candidate_pois, start_location, window_start_min, context
                )
                if cand_itinerary and self._is_better(cand_itinerary, best_itinerary):
                    new_unvisited = [p for p in unvisited if p.id != cand.id] + [old_poi]
                    return cand_itinerary, new_unvisited
        return None, unvisited

    def _try_candidate_insert(
        self,
        current_pois: List[POI],
        unvisited: List[POI],
        start_location: Coordinates,
        window_start_min: int,
        context: FeasibilityContext,
        best_itinerary: Itinerary,
    ) -> Tuple[Optional[Itinerary], List[POI]]:
        for i in range(len(current_pois) + 1):
            for cand in unvisited:
                candidate_pois = current_pois[:i] + [cand] + current_pois[i:]
                cand_itinerary = self._evaluate_route(
                    candidate_pois, start_location, window_start_min, context
                )
                if cand_itinerary and self._is_better(cand_itinerary, best_itinerary):
                    new_unvisited = [p for p in unvisited if p.id != cand.id]
                    return cand_itinerary, new_unvisited
        return None, unvisited

    def _local_search_step(
        self,
        current_pois: List[POI],
        unvisited: List[POI],
        start_location: Coordinates,
        window_start_min: int,
        context: FeasibilityContext,
        best_itinerary: Itinerary,
    ) -> Optional[Tuple[Itinerary, List[POI]]]:
        cand_2opt = self._try_2opt_improvement(
            current_pois, start_location, window_start_min, context, best_itinerary
        )
        if cand_2opt:
            return cand_2opt, unvisited

        cand_swap = self._try_swap_improvement(
            current_pois, start_location, window_start_min, context, best_itinerary
        )
        if cand_swap:
            return cand_swap, unvisited

        cand_repl, new_unvisited = self._try_candidate_swap(
            current_pois, unvisited, start_location, window_start_min, context, best_itinerary
        )
        if cand_repl:
            return cand_repl, new_unvisited

        cand_ins, new_unvisited_ins = self._try_candidate_insert(
            current_pois, unvisited, start_location, window_start_min, context, best_itinerary
        )
        if cand_ins:
            return cand_ins, new_unvisited_ins

        return None

    def _local_search(
        self,
        initial_itinerary: Itinerary,
        remaining_candidates: List[POI],
        start_location: Coordinates,
        window_start_min: int,
        context: FeasibilityContext,
        max_iterations: int = 50,
    ) -> Itinerary:
        best_itinerary = initial_itinerary
        current_pois = [s.poi for s in best_itinerary.stops]
        unvisited = list(remaining_candidates)

        for _ in range(max_iterations):
            step = self._local_search_step(
                current_pois,
                unvisited,
                start_location,
                window_start_min,
                context,
                best_itinerary,
            )
            if step is None:
                break
            best_itinerary, unvisited = step
            current_pois = [s.poi for s in best_itinerary.stops]

        return best_itinerary


def _unique_pois(candidate_pois: list[POI]) -> list[POI]:
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
    start_location: Coordinates | None = None,
) -> Itinerary:
    durations: Mapping[str, int] = visit_durations or {}
    stops: list[RouteStop] = []
    cursor = start_time
    for poi in sequence:
        duration_minutes = durations.get(poi.id, poi.stay_duration_minutes)
        stops.append(
            RouteStop(poi=poi, start=cursor, duration_minutes=duration_minutes)
        )
        cursor = cursor + timedelta(minutes=duration_minutes + travel_time_minutes)
    return Itinerary(stops=stops, start_location=start_location)


def _is_feasible(
    sequence: list[POI],
    start_time: datetime,
    travel_time_minutes: float,
    availability_window: TimeWindow,
    visit_durations: Mapping[str, int] | None = None,
) -> bool:
    itinerary = _simulate(sequence, start_time, travel_time_minutes, visit_durations)
    return ScheduleService.validate_itinerary(itinerary, availability_window) == []


def _completion(itinerary: Itinerary, start_time: datetime) -> datetime:
    if not itinerary.stops:
        return start_time
    last_stop = itinerary.stops[-1]
    end_time = (
        last_stop.end if hasattr(last_stop, "end") else getattr(last_stop, "departure_time", None)
    )
    if isinstance(end_time, datetime):
        return end_time
    if isinstance(end_time, time):
        return datetime.combine(start_time.date(), end_time)
    return start_time


def _route_completion(
    sequence: list[POI],
    start_time: datetime,
    travel_time_minutes: float,
    visit_durations: Mapping[str, int] | None = None,
) -> datetime:
    return _completion(
        _simulate(sequence, start_time, travel_time_minutes, visit_durations),
        start_time,
    )


def _weight(poi: POI, marginal_cost: float) -> float:
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


def _local_search_contingency(
    route: list[POI],
    start_time: datetime,
    travel_time_minutes: float,
    availability_window: TimeWindow,
    visit_durations: Mapping[str, int] | None = None,
) -> int:
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
