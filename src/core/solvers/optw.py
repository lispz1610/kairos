from __future__ import annotations

import math
from datetime import time
from typing import List, Optional, Tuple

from src.core.domain.models import (
    POI,
    Coordinates,
    Itinerary,
    ItineraryStop,
    PreferencesProfile,
    TimeWindow,
)


def haversine_distance_km(coord1: Coordinates, coord2: Coordinates) -> float:
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
    dist = haversine_distance_km(coord1, coord2)
    minutes = int(math.ceil((dist / speed_kmh) * 60.0))
    return max(2, minutes)


def minutes_to_time(minutes_since_midnight: int) -> time:
    normalized = minutes_since_midnight % (24 * 60)
    hours = normalized // 60
    minutes = normalized % 60
    return time(hour=hours, minute=minutes)


def time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


class OPTWSolver:
    """Solver heurístico para Orienteering Problem with Time Windows (OPTW).

    Maximiza utilidade acumulada respeitando horários de funcionamento,
    janela diária e slots reservados para refeições.
    """

    def __init__(self, transit_speed_kmh: float = 25.0) -> None:
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
        if not candidates:
            return Itinerary(stops=[], total_utility=0.0, total_duration_minutes=0)

        effective_candidates = self._prepare_candidates(candidates, preferences)
        reserved_ranges = self._convert_reserved_slots(reserved_slots)

        window_start_min = time_to_minutes(window.start_time)
        window_end_min = time_to_minutes(window.end_time)

        current_location = start_location
        current_time_min = window_start_min
        remaining_candidates = list(effective_candidates)
        selected_stops: List[ItineraryStop] = []
        total_utility = 0.0

        while remaining_candidates:
            best = self._find_best_candidate(
                current_location=current_location,
                current_time_min=current_time_min,
                end_location=end_location,
                window_end_min=window_end_min,
                candidates=remaining_candidates,
                reserved_ranges=reserved_ranges,
            )
            if best is None:
                break

            poi, arr_min, dep_min, transit_min = best
            selected_stops.append(
                ItineraryStop(
                    poi=poi,
                    arrival_time=minutes_to_time(arr_min),
                    departure_time=minutes_to_time(dep_min),
                    transit_duration_minutes=transit_min,
                )
            )
            total_utility += poi.utility_score
            current_location = poi.location
            current_time_min = dep_min
            remaining_candidates.remove(poi)

        final_transit = (
            estimate_transit_minutes(current_location, end_location, self.transit_speed_kmh)
            if selected_stops
            else 0
        )
        total_duration = (current_time_min + final_transit) - window_start_min

        return Itinerary(
            stops=selected_stops,
            total_utility=total_utility,
            total_duration_minutes=max(0, total_duration),
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
        return [
            (time_to_minutes(s.start_time), time_to_minutes(s.end_time))
            for s in reserved_slots
        ]

    def _find_best_candidate(
        self,
        current_location: Coordinates,
        current_time_min: int,
        end_location: Coordinates,
        window_end_min: int,
        candidates: List[POI],
        reserved_ranges: List[Tuple[int, int]],
    ) -> Optional[Tuple[POI, int, int, int]]:
        best_candidate: Optional[POI] = None
        best_score = -1.0
        best_arrival = 0
        best_departure = 0
        best_transit = 0

        for poi in candidates:
            transit_min = estimate_transit_minutes(
                current_location, poi.location, self.transit_speed_kmh
            )
            arr_min = current_time_min + transit_min
            poi_open = time_to_minutes(poi.window.start_time)
            poi_close = time_to_minutes(poi.window.end_time)

            srv_start = max(arr_min, poi_open)
            dep_min = srv_start + poi.stay_duration_minutes

            if not self._is_feasible(
                dep_min=dep_min,
                poi_close=poi_close,
                poi_loc=poi.location,
                end_loc=end_location,
                window_end_min=window_end_min,
                srv_start=srv_start,
                reserved_ranges=reserved_ranges,
            ):
                continue

            wait_min = max(0, poi_open - arr_min)
            total_time = float(transit_min + poi.stay_duration_minutes + wait_min)
            score = poi.utility_score / max(1.0, total_time)
            if score > best_score:
                best_score = score
                best_candidate = poi
                best_arrival = arr_min
                best_departure = dep_min
                best_transit = transit_min

        if best_candidate is None:
            return None
        return (best_candidate, best_arrival, best_departure, best_transit)

    def _is_feasible(
        self,
        dep_min: int,
        poi_close: int,
        poi_loc: Coordinates,
        end_loc: Coordinates,
        window_end_min: int,
        srv_start: int,
        reserved_ranges: List[Tuple[int, int]],
    ) -> bool:
        if dep_min > poi_close:
            return False

        ret_transit = estimate_transit_minutes(poi_loc, end_loc, self.transit_speed_kmh)
        if dep_min + ret_transit > window_end_min:
            return False

        # Evita sobreposição com slots reservados de refeição
        for r_start, r_end in reserved_ranges:
            if not (dep_min <= r_start or srv_start >= r_end):
                return False

        return True
