from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.adapters.places import (
    CachedPlacesAdapter,
    OfflineReplayPlacesAdapter,
    create_places_adapter,
)
from src.core.domain.models import POI, Coordinates, CurationList
from src.core.ports.places import PlacesPort
from src.core.services.curation import CurationService


class DummyPlacesPort(PlacesPort):
    """Porta de lugares falsa que registra o número de chamadas para testes."""

    def __init__(self) -> None:
        """Inicializa os contadores de chamadas da porta falsa."""
        self.curated_call_count = 0
        self.search_call_count = 0

    def get_curated_lists(self, city_name: str) -> list[CurationList]:
        """Retorna uma Lista de Curadoria fictícia e registra a chamada."""
        self.curated_call_count += 1
        return [
            CurationList(
                id="dummy-1",
                title=f"Lista de {city_name}",
                items=[
                    POI(
                        id="dummy-poi",
                        name="Lugar Dummy",
                        location=Coordinates(latitude=0.0, longitude=0.0),
                    )
                ],
            )
        ]

    def search_places(
        self, query: str, city_name: str | None = None
    ) -> list[POI]:
        """Retorna um Ponto de Interesse fictício e registra a chamada."""
        self.search_call_count += 1
        return [
            POI(
                id=f"poi-{query}",
                name=f"Nome {query}",
                location=Coordinates(latitude=1.0, longitude=1.0),
            )
        ]


def test_curation_service_with_injected_port() -> None:
    """Verifica que o serviço delega à porta injetada."""
    port = DummyPlacesPort()
    service = CurationService(places_port=port)

    lists = service.get_suggested_curation_lists("Belo Horizonte")
    assert len(lists) == 1
    assert lists[0].title == "Lista de Belo Horizonte"
    assert port.curated_call_count == 1

    pois = service.search_places_autocomplete("Café", "Belo Horizonte")
    assert len(pois) == 1
    assert pois[0].id == "poi-Café"
    assert port.search_call_count == 1


def test_curation_service_default_instantiation() -> None:
    """Verifica que o serviço usa uma porta padrão com curadorias sugeridas."""
    service = CurationService()
    assert isinstance(service.places_port, PlacesPort)
    sp_lists = service.get_suggested_curation_lists("São Paulo")
    assert len(sp_lists) >= 3


def test_apply_curation_boost_to_matching_pois() -> None:
    """Verifica o aumento da Pontuação de Utilidade apenas para Pontos de Interesse curados."""
    service = CurationService()
    poi_michelin = POI(
        id="dom",
        name="D.O.M.",
        location=Coordinates(latitude=-23.56, longitude=-46.66),
        utility_score=10.0,
        awards=["Michelin 2 Estrelas"],
    )
    poi_regular = POI(
        id="reg",
        name="Lanchonete Comum",
        location=Coordinates(latitude=-23.56, longitude=-46.66),
        utility_score=5.0,
    )

    custom_list = CurationList(
        id="cl-1",
        title="Meus Favoritos",
        items=[poi_michelin],
    )

    # Empty active lists returns unchanged
    assert service.apply_curation_boost([poi_michelin], []) == [poi_michelin]

    boosted = service.apply_curation_boost([poi_michelin, poi_regular], [custom_list])
    b_dom = next(p for p in boosted if p.id == "dom")
    b_reg = next(p for p in boosted if p.id == "reg")

    assert b_dom.utility_score == 15.0
    assert b_reg.utility_score == 5.0

    # Inactive curation list should not boost POIs
    inactive_list = CurationList(
        id="cl-inactive",
        title="Lista Desativada",
        items=[poi_michelin],
        is_active=False,
    )
    unboosted = service.apply_curation_boost(
        [poi_michelin, poi_regular], [inactive_list]
    )
    u_dom = next(p for p in unboosted if p.id == "dom")
    assert u_dom.utility_score == 10.0

    # Custom list with notes and lowercase name matching
    poi_named = POI(
        id="different-id",
        name="d.o.m.",
        location=Coordinates(latitude=-23.56, longitude=-46.66),
        utility_score=6.0,
        notes="Dica do chef",
    )
    boosted_named = service.apply_curation_boost([poi_named], [custom_list])
    assert boosted_named[0].utility_score == 9.0


def test_offline_replay_adapter_curated_lists() -> None:
    """Verifica as Listas de Curadoria em modo de reprodução offline."""
    adapter = OfflineReplayPlacesAdapter()

    sp_lists = adapter.get_curated_lists("São Paulo")
    assert len(sp_lists) >= 3
    titles = [cl.title for cl in sp_lists]
    assert any("Michelin" in t for t in titles)

    # Case insensitivity
    lima_lists = adapter.get_curated_lists("lima")
    assert len(lima_lists) >= 2
    assert any("50 Best" in cl.title for cl in lima_lists)

    # Unknown city
    unknown = adapter.get_curated_lists("Atlantida")
    assert unknown == []


def test_offline_replay_adapter_search_places() -> None:
    """Verifica a busca de Pontos de Interesse em modo de reprodução offline."""
    adapter = OfflineReplayPlacesAdapter()

    # Search with city filter
    results = adapter.search_places("Coffee", "São Paulo")
    assert len(results) >= 1
    assert any("Coffee Lab" in p.name for p in results)

    # Search by category (e.g. bakery)
    bakery_results = adapter.search_places("bakery", "São Paulo")
    assert len(bakery_results) >= 1
    assert any("Fabrique" in p.name for p in bakery_results)

    # Search across all cities
    all_results = adapter.search_places("Central")
    assert len(all_results) >= 1
    assert any("Central" in p.name for p in all_results)

    # Empty query or not found
    assert adapter.search_places("") == []
    assert adapter.search_places("NonExistentPlaceXYZ123") == []


def test_cached_places_adapter_cache_aside_sqlite() -> None:
    """Verifica o padrão cache-aside em SQLite e a limpeza do cache."""
    port = DummyPlacesPort()
    cached_adapter = CachedPlacesAdapter(
        api_key=None,
        cache_path=":memory:",
        fallback_adapter=port,
    )

    # 1st call: Miss, delegates to fallback
    res1 = cached_adapter.get_curated_lists("Curitiba")
    assert len(res1) == 1
    assert port.curated_call_count == 1

    # 2nd call: Hit, served from SQLite cache
    res2 = cached_adapter.get_curated_lists("Curitiba")
    assert len(res2) == 1
    assert res2[0].id == res1[0].id
    assert port.curated_call_count == 1  # Not incremented!

    # Search places cache-aside
    s1 = cached_adapter.search_places("Pizza", "Curitiba")
    assert len(s1) == 1
    assert port.search_call_count == 1

    s2 = cached_adapter.search_places("Pizza", "Curitiba")
    assert len(s2) == 1
    assert s2[0].id == s1[0].id
    assert port.search_call_count == 1  # Not incremented!

    # Empty query returns empty and does not query fallback
    assert cached_adapter.search_places("") == []

    # Clear cache resets entries
    cached_adapter.clear_cache()
    cached_adapter.get_curated_lists("Curitiba")
    assert port.curated_call_count == 2


def test_cached_places_adapter_with_external_api_mock() -> None:
    """Verifica o uso da API externa e o fallback quando ela falha."""
    port = DummyPlacesPort()
    cached_adapter = CachedPlacesAdapter(
        api_key="test_google_key",
        cache_path=":memory:",
        fallback_adapter=port,
    )

    mock_google_response = {
        "results": [
            {
                "place_id": "google-1",
                "name": "Google Cafe",
                "geometry": {"location": {"lat": -23.5, "lng": -46.6}},
                "types": ["cafe"],
                "rating": 4.9,
                "price_level": 2,
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_google_response
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_resp):
        res = cached_adapter.search_places("Google", "São Paulo")
        assert len(res) == 1
        assert res[0].id == "google-1"
        assert res[0].name == "Google Cafe"
        assert port.search_call_count == 0  # External API succeeded, fallback not called!

    # Test external API failure triggers fallback
    cached_adapter.clear_cache()
    with patch("httpx.get", side_effect=Exception("Network error")):
        fallback_res = cached_adapter.search_places("Google", "São Paulo")
        assert len(fallback_res) == 1
        assert port.search_call_count == 1  # Fallback called!


def test_create_places_adapter_factory(tmp_path: Path) -> None:
    """Verifica que a fábrica cria o adaptador com cache no caminho informado."""
    cache_file = tmp_path / "custom_cache.db"
    adapter = create_places_adapter(cache_path=cache_file)
    assert isinstance(adapter, CachedPlacesAdapter)
    assert Path(cache_file).exists()
