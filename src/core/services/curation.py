from __future__ import annotations

from typing import List, Optional

from src.core.domain.models import POI, CurationList
from src.core.ports.places import PlacesPort


class CurationService:
    """Gerencia listas de curadoria pública e listas personalizadas do usuário."""

    def __init__(self, places_port: Optional[PlacesPort] = None) -> None:
        if places_port is not None:
            self.places_port = places_port
        else:
            from src.adapters.places import create_places_adapter

            self.places_port = create_places_adapter()

    def get_suggested_curation_lists(self, city_name: str) -> List[CurationList]:
        return self.places_port.get_curated_lists(city_name)

    def search_places_autocomplete(
        self, query: str, city_name: Optional[str] = None
    ) -> List[POI]:
        return self.places_port.search_places(query, city_name)

    def _extract_curated_keys(
        self, curation_lists: List[CurationList]
    ) -> tuple[set[str], set[str]]:
        curated_ids = {item.id for cl in curation_lists for item in cl.items}
        curated_names = {item.name.lower() for cl in curation_lists for item in cl.items}
        return curated_ids, curated_names

    def _boost_poi(
        self,
        poi: POI,
        curated_ids: set[str],
        curated_names: set[str],
        boost_multiplier: float,
    ) -> POI:
        is_curated = poi.id in curated_ids or poi.name.lower() in curated_names
        if not is_curated:
            return poi
        return poi.model_copy(
            update={"utility_score": poi.utility_score * boost_multiplier}
        )

    def apply_curation_boost(
        self,
        candidates: List[POI],
        active_curation_lists: List[CurationList],
        boost_multiplier: float = 1.5,
    ) -> List[POI]:
        if not active_curation_lists:
            return candidates

        effective_lists = [
            cl for cl in active_curation_lists if getattr(cl, "is_active", True)
        ]
        if not effective_lists:
            return candidates

        curated_ids, curated_names = self._extract_curated_keys(effective_lists)

        return [
            self._boost_poi(poi, curated_ids, curated_names, boost_multiplier)
            for poi in candidates
        ]
