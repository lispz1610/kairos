from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from src.core.domain.models import POI, CurationList


class PlacesPort(ABC):
    """Porta abstrata para catálogo de estabelecimentos e listas de curadoria."""

    @abstractmethod
    def get_curated_lists(self, city_name: str) -> List[CurationList]:
        """Recupera listas curadas sugeridas para uma determinada cidade."""
        pass

    @abstractmethod
    def search_places(
        self, query: str, city_name: Optional[str] = None
    ) -> List[POI]:
        """Pesquisa estabelecimentos/POIs por nome ou categoria, opcionalmente por cidade."""
        pass
