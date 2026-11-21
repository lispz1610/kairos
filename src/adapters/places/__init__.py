from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from src.adapters.places.cached_adapter import CachedPlacesAdapter
from src.adapters.places.offline_adapter import OfflineReplayPlacesAdapter
from src.core.ports.places import PlacesPort
from src.core.services.curation import set_default_places_port_factory


def create_places_adapter(
    api_key: Optional[str] = None,
    cache_path: Optional[Path | str] = None,
    fallback_adapter: Optional[PlacesPort] = None,
) -> PlacesPort:
    """Cria e retorna a implementação de PlacesPort configurada com Cache-Aside e Offline Replay."""
    key = api_key if api_key is not None else os.getenv("GOOGLE_MAPS_API_KEY")
    return CachedPlacesAdapter(
        api_key=key,
        cache_path=cache_path,
        fallback_adapter=fallback_adapter,
    )


# Registra a fábrica padrão para o CurationService sem que o core precise importar este módulo
set_default_places_port_factory(create_places_adapter)


__all__ = [
    "PlacesPort",
    "OfflineReplayPlacesAdapter",
    "CachedPlacesAdapter",
    "create_places_adapter",
]
