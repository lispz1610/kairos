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

    def apply_curation_boost(
        self,
        candidates: List[POI],
        active_curation_lists: List[CurationList],
        boost_multiplier: float = 1.5,
    ) -> List[POI]:
        if not active_curation_lists:
            return candidates

        # Conjunto de IDs e nomes curados
        curated_ids = {
            item.id for cl in active_curation_lists for item in cl.items
        }
        curated_names = {
            item.name.lower() for cl in active_curation_lists for item in cl.items
        }

        boosted_list: List[POI] = []
        for poi in candidates:
            is_curated = (
                poi.id in curated_ids or poi.name.lower() in curated_names
            )
            if is_curated:
                boosted_poi = poi.model_copy(
                    update={"utility_score": poi.utility_score * boost_multiplier}
                )
                boosted_list.append(boosted_poi)
            else:
                boosted_list.append(poi)

        return boosted_list
