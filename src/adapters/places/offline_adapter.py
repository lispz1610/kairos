from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from src.adapters.places.fixtures.mock_catalog import load_mock_catalog
from src.core.domain.models import POI, CurationList
from src.core.ports.places import PlacesPort


class OfflineReplayPlacesAdapter(PlacesPort):
    """Adaptador de lugares offline baseado em fixtures locais estruturadas (ADR 0005)."""

    def __init__(
        self,
        catalog: Optional[Dict[str, List[CurationList]]] = None,
        fixtures_path: Optional[Path | str] = None,
    ) -> None:
        if catalog is not None:
            self._catalog = catalog
        else:
            self._catalog = load_mock_catalog(fixtures_path)

    def get_curated_lists(self, city_name: str) -> List[CurationList]:
        target = city_name.strip().lower()
        for city, lists in self._catalog.items():
            if city.lower() == target:
                return lists
        return []

    def _city_matches(self, city: str, city_norm: Optional[str]) -> bool:
        return city_norm is None or city.lower() == city_norm

    def _matches_query(self, item: POI, query_norm: str) -> bool:
        return query_norm in item.name.lower() or query_norm in item.category.lower()

    def search_places(
        self, query: str, city_name: Optional[str] = None
    ) -> List[POI]:
        query_norm = query.strip().lower()
        if not query_norm:
            return []

        city_norm = city_name.strip().lower() if city_name else None
        results: List[POI] = []

        for city, lists in self._catalog.items():
            if not self._city_matches(city, city_norm):
                continue
            for cl in lists:
                results.extend(
                    item for item in cl.items if self._matches_query(item, query_norm)
                )

        return results[:5]
