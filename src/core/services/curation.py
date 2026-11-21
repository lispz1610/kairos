from __future__ import annotations

from typing import Callable, List, Optional

from src.core.domain.models import POI, CurationList
from src.core.ports.places import PlacesPort

_default_places_port_factory: Optional[Callable[[], PlacesPort]] = None


def set_default_places_port_factory(
    factory: Optional[Callable[[], PlacesPort]],
) -> None:
    """Registra uma fábrica padrão para criar instâncias de PlacesPort sem acoplar o Core."""
    global _default_places_port_factory
    _default_places_port_factory = factory


def get_default_places_port_factory() -> Optional[Callable[[], PlacesPort]]:
    """Retorna a fábrica padrão registrada para PlacesPort."""
    return _default_places_port_factory


class CurationService:
    """Gerencia listas de curadoria pública e listas personalizadas do usuário."""

    def __init__(self, places_port: Optional[PlacesPort] = None) -> None:
        """Inicializar o serviço com a porta informada ou a fábrica padrão registrada.

        Levanta ValueError quando nenhuma das duas está disponível.
        """
        if places_port is not None:
            self.places_port = places_port
        elif _default_places_port_factory is not None:
            self.places_port = _default_places_port_factory()
        else:
            raise ValueError(
                "places_port é obrigatório ou uma fábrica padrão deve ser configurada."
            )

    def get_suggested_curation_lists(self, city_name: str) -> List[CurationList]:
        """Retorna listas de curadoria sugeridas para a cidade especificada."""
        return self.places_port.get_curated_lists(city_name)

    def search_places_autocomplete(
        self, query: str, city_name: Optional[str] = None
    ) -> List[POI]:
        """Executa busca de estabelecimentos e atrações para preenchimento automático."""
        return self.places_port.search_places(query, city_name)

    def _extract_curated_keys(
        self, curation_lists: List[CurationList]
    ) -> tuple[set[str], set[str]]:
        curated_ids = {
            item.id for curation_list in curation_lists for item in curation_list.items
        }
        curated_names = {
            item.name.lower()
            for curation_list in curation_lists
            for item in curation_list.items
        }
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
        """Aplica bonificação de utilidade a candidatos presentes em listas ativas."""
        if not active_curation_lists:
            return candidates

        effective_lists = [
            curation_list
            for curation_list in active_curation_lists
            if getattr(curation_list, "is_active", True)
        ]
        if not effective_lists:
            return candidates

        curated_ids, curated_names = self._extract_curated_keys(effective_lists)

        return [
            self._boost_poi(poi, curated_ids, curated_names, boost_multiplier)
            for poi in candidates
        ]
