from __future__ import annotations

import math
from datetime import time
from typing import Any, List, Optional

from src.core.domain.models import POI, Coordinates, Itinerary, ItineraryStop, TimeWindow


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

    Maximiza utilidade acumulada respeitando horários de funcionamento e janela diária.
    """

    def __init__(self, transit_speed_kmh: float = 25.0) -> None:
        self.transit_speed_kmh = transit_speed_kmh

    def solve(
        self,
        start_location: Coordinates,
        end_location: Coordinates,
        window: TimeWindow,
        candidates: List[POI],
        preferences: Optional[Any] = None,
    ) -> Itinerary:
        if not candidates:
            return Itinerary(stops=[], total_utility=0.0, total_duration_minutes=0)

        # Se houver perfil de preferências, pondera a utilidade
        from src.core.services.preferences import PreferencesService

        effective_candidates = candidates
        if preferences is not None:
            effective_candidates = PreferencesService().apply_preference_weights(
                candidates, preferences
            )

        window_start_min = time_to_minutes(window.start_time)
        window_end_min = time_to_minutes(window.end_time)

        current_location = start_location
        current_time_min = window_start_min
        remaining_candidates = list(effective_candidates)
        selected_stops: List[ItineraryStop] = []
        total_utility = 0.0

        while remaining_candidates:
            best_candidate: Optional[POI] = None
            best_score = -1.0
            best_arrival_min = 0
            best_departure_min = 0
            best_transit_min = 0

            for poi in remaining_candidates:
                transit_min = estimate_transit_minutes(
                    current_location, poi.location, self.transit_speed_kmh
                )
                arrival_min = current_time_min + transit_min

                poi_open_min = time_to_minutes(poi.window.start_time)
                poi_close_min = time_to_minutes(poi.window.end_time)

                service_start_min = max(arrival_min, poi_open_min)
                departure_min = service_start_min + poi.stay_duration_minutes

                # Checagem de viabilidade do POI
                if departure_min > poi_close_min:
                    continue

                # Checagem de retorno ao depósito final antes do término da janela
                return_transit_min = estimate_transit_minutes(
                    poi.location, end_location, self.transit_speed_kmh
                )
                if departure_min + return_transit_min > window_end_min:
                    continue

                wait_min = max(0, poi_open_min - arrival_min)
                marginal_cost = transit_min + poi.stay_duration_minutes + wait_min
                score = poi.utility_score / max(1.0, float(marginal_cost))

                if score > best_score:
                    best_score = score
                    best_candidate = poi
                    best_arrival_min = arrival_min
                    best_departure_min = departure_min
                    best_transit_min = transit_min

            if best_candidate is None:
                break

            selected_stops.append(
                ItineraryStop(
                    poi=best_candidate,
                    arrival_time=minutes_to_time(best_arrival_min),
                    departure_time=minutes_to_time(best_departure_min),
                    transit_duration_minutes=best_transit_min,
                )
            )
            total_utility += best_candidate.utility_score
            current_location = best_candidate.location
            current_time_min = best_departure_min
            remaining_candidates.remove(best_candidate)

        # Adiciona o retorno final ao cálculo da duração
        final_transit_min = (
            estimate_transit_minutes(current_location, end_location, self.transit_speed_kmh)
            if selected_stops
            else 0
        )
        total_duration = (current_time_min + final_transit_min) - window_start_min

        return Itinerary(
            stops=selected_stops,
            total_utility=total_utility,
            total_duration_minutes=max(0, total_duration),
        )
