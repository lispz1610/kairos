from __future__ import annotations

import importlib
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.adapters.places.cached_adapter import CachedPlacesAdapter
from src.adapters.web.app import app
from src.core.domain.models import POI, Coordinates
from src.core.services.curation import CurationService

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_places_adapter(monkeypatch, tmp_path: Path) -> Iterator[CachedPlacesAdapter]:
    """Usar um cache SQLite exclusivo por caso de integração."""
    web_module = importlib.import_module("src.adapters.web.app")
    adapter = CachedPlacesAdapter(api_key="", cache_path=tmp_path / "places.db")
    monkeypatch.setattr(web_module, "places_adapter", adapter)
    monkeypatch.setattr(web_module, "curation_service", CurationService(places_port=adapter))
    yield adapter
    adapter._conn.close()


@pytest.mark.requirement("RF05")
@pytest.mark.parametrize("name", ["primeira execução", "segunda execução"])
def test_places_cache_is_independent_between_cases(monkeypatch, name: str) -> None:
    """Consultas idênticas em casos distintos recebem seus próprios dados."""
    web_module = importlib.import_module("src.adapters.web.app")
    poi = POI(id="isolated", name=name, location=Coordinates(latitude=0, longitude=0))
    fallback = SimpleNamespace(search_places=lambda query, city: [poi])
    monkeypatch.setattr(web_module.places_adapter, "fallback_adapter", fallback)

    response = client.get("/api/places/search?query=isolation_probe_104")

    assert response.status_code == 200
    assert response.json()[0]["name"] == name


@pytest.mark.requirement("RF05")
def test_suggested_curation_endpoint() -> None:
    # Test São Paulo
    """Verifica que a Lista de Curadoria sugerida é retornada para São Paulo e Lima."""
    response_sp = client.get("/api/curation/suggested?city_name=São%20Paulo")
    assert response_sp.status_code == 200
    data_sp = response_sp.json()
    assert len(data_sp) >= 2
    titles_sp = [item["title"] for item in data_sp]
    assert any("Michelin" in t for t in titles_sp)

    # Test Lima
    response_lima = client.get("/api/curation/suggested?city_name=Lima")
    assert response_lima.status_code == 200
    data_lima = response_lima.json()
    assert len(data_lima) >= 2
    titles_lima = [item["title"] for item in data_lima]
    assert any("50 Best" in t for t in titles_lima)


@pytest.mark.requirement("RF05")
def test_places_search_autocomplete_endpoint() -> None:
    # Search with city
    """Verifica a busca de Pontos de Interesse por cidade, globalmente e sem resultados."""
    response = client.get("/api/places/search?query=Coffee&city_name=São%20Paulo")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert "Coffee" in data[0]["name"] or "Coffee" in data[0]["category"]

    # Search across all cities
    response_all = client.get("/api/places/search?query=Central")
    assert response_all.status_code == 200
    data_all = response_all.json()
    assert len(data_all) >= 1
    assert any("Central" in p["name"] for p in data_all)

    # Unknown place
    response_empty = client.get("/api/places/search?query=InexistentPlace12345")
    assert response_empty.status_code == 200
    assert response_empty.json() == []


@pytest.mark.requirement("RF05")
def test_cache_persistence_and_offline_replay(
    isolated_places_adapter: CachedPlacesAdapter,
    monkeypatch,
) -> None:
    # Query twice to exercise Cache-Aside
    """Verifica que consultas repetidas são servidas pelo cache e reproduzidas offline."""
    resp1 = client.get("/api/places/search?query=Fabrique&city_name=São%20Paulo")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1) >= 1

    resp2 = client.get("/api/places/search?query=Fabrique&city_name=São%20Paulo")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data1 == data2

    # A resposta permanece disponível pelo contrato público mesmo sem o fallback.
    def unavailable_fallback(query: str, city: str | None) -> list[POI]:
        raise AssertionError("cache miss inesperado")

    monkeypatch.setattr(
        isolated_places_adapter,
        "fallback_adapter",
        SimpleNamespace(search_places=unavailable_fallback),
    )
    replay = client.get("/api/places/search?query=Fabrique&city_name=São%20Paulo")
    assert replay.status_code == 200
    assert replay.json() == data1


@pytest.mark.requirement("RF05")
def test_concurrent_places_caches_remain_isolated(tmp_path: Path) -> None:
    """Consultas simultâneas idênticas preservam os dados de cada banco SQLite."""
    barrier = Barrier(2)

    def search(name: str) -> str:
        poi = POI(id="same-id", name=name, location=Coordinates(latitude=0, longitude=0))
        fallback = SimpleNamespace(search_places=lambda query, city: [poi])
        adapter = CachedPlacesAdapter(
            api_key="", cache_path=tmp_path / name / "places.db", fallback_adapter=fallback
        )
        try:
            barrier.wait(timeout=5)
            first = adapter.search_places("same-query", "São Paulo")

            def unavailable_fallback(query: str, city: str | None) -> list[POI]:
                raise AssertionError("cache miss inesperado")

            adapter.fallback_adapter = SimpleNamespace(search_places=unavailable_fallback)
            replay = adapter.search_places("same-query", "São Paulo")
            assert [item.name for item in replay] == [name]
            return first[0].name
        finally:
            adapter._conn.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(search, ["primeiro", "segundo"]))
    assert results == ["primeiro", "segundo"]


@pytest.mark.requirement("RF04")
def test_optimize_endpoint_applies_curation_boost() -> None:
    """Verifica que curadoria ativa aumenta a Pontuação de Utilidade e altera o Roteiro."""
    hotel_loc = {"latitude": -23.5500, "longitude": -46.6300}
    # Two candidates: poi-a has base utility 10.0, poi-b has base utility 12.0
    # Candidate time window allows only 1 attraction
    candidates = [
        {
            "id": "poi-a",
            "name": "Museu Menor Curado",
            "location": {"latitude": -23.5520, "longitude": -46.6320},
            "stay_duration_minutes": 180,
            "utility_score": 10.0,
        },
        {
            "id": "poi-b",
            "name": "Parque Maior Padrao",
            "location": {"latitude": -23.5530, "longitude": -46.6330},
            "stay_duration_minutes": 180,
            "utility_score": 12.0,
        },
    ]

    base_payload = {
        "start_location": hotel_loc,
        "end_location": hotel_loc,
        "window": {"start_time": "14:00:00", "end_time": "18:00:00"},
        "candidates": candidates,
    }

    # Without curation list, poi-b (utility 12) is picked over poi-a (utility 10)
    resp_unboosted = client.post("/api/trip/optimize", json=base_payload)
    assert resp_unboosted.status_code == 200
    it_unboosted = resp_unboosted.json()
    assert len(it_unboosted["stops"]) == 1
    assert it_unboosted["stops"][0]["poi"]["id"] == "poi-b"

    # With curation list containing poi-a, poi-a utility becomes 10 * 1.5 = 15.0 > 12.0
    curation_list = {
        "id": "cl-favorites",
        "title": "Meus Favoritos",
        "items": [candidates[0]],
        "is_active": True,
    }
    boosted_payload = {
        **base_payload,
        "curation_lists": [curation_list],
    }
    resp_boosted = client.post("/api/trip/optimize", json=boosted_payload)
    assert resp_boosted.status_code == 200
    it_boosted = resp_boosted.json()
    assert len(it_boosted["stops"]) == 1
    assert it_boosted["stops"][0]["poi"]["id"] == "poi-a"
    assert it_boosted["stops"][0]["poi"]["utility_score"] == 15.0


@pytest.mark.requirement("RF04")
def test_optimize_endpoint_respects_inactive_curation_list() -> None:
    """Verifica que Lista de Curadoria inativa não altera a Pontuação de Utilidade."""
    hotel_loc = {"latitude": -23.5500, "longitude": -46.6300}
    candidates = [
        {
            "id": "poi-x",
            "name": "Local X",
            "location": {"latitude": -23.5520, "longitude": -46.6320},
            "stay_duration_minutes": 180,
            "utility_score": 10.0,
        },
        {
            "id": "poi-y",
            "name": "Local Y",
            "location": {"latitude": -23.5530, "longitude": -46.6330},
            "stay_duration_minutes": 180,
            "utility_score": 12.0,
        },
    ]

    inactive_list = {
        "id": "cl-off",
        "title": "Desativada",
        "items": [candidates[0]],
        "is_active": False,
    }

    payload = {
        "start_location": hotel_loc,
        "end_location": hotel_loc,
        "window": {"start_time": "14:00:00", "end_time": "18:00:00"},
        "candidates": candidates,
        "curation_lists": [inactive_list],
    }

    resp = client.post("/api/trip/optimize", json=payload)
    assert resp.status_code == 200
    it = resp.json()
    assert len(it["stops"]) == 1
    # When inactive, poi-x remains at 10.0 and poi-y (12.0) is picked
    assert it["stops"][0]["poi"]["id"] == "poi-y"


@pytest.mark.requirement("RF05")
def test_dining_recommend_with_curation_boost() -> None:
    """Verifica que a curadoria ativa reordena as recomendações de restaurantes."""
    ref_loc = {"latitude": -23.5600, "longitude": -46.6500}
    # Two restaurants at similar proximity (~0.3 km)
    # rest-normal has slightly higher rating (4.8 vs 4.6)
    # rest-curated has base utility 10.0, will be boosted to 15.0
    r_normal = {
        "id": "rest-normal",
        "name": "Restaurante Normal",
        "location": {"latitude": -23.5620, "longitude": -46.6520},
        "category": "restaurant",
        "rating": 4.8,
        "price_tier": "$$",
        "utility_score": 1.0,
    }
    r_curated = {
        "id": "rest-curated",
        "name": "Bistrô Especial da Curadoria",
        "location": {"latitude": -23.5620, "longitude": -46.6520},
        "category": "restaurant",
        "rating": 4.6,
        "price_tier": "$$",
        "utility_score": 5.0,
    }

    curation_list = {
        "id": "cl-gourmet",
        "title": "Guia Gastronômico",
        "items": [r_curated],
        "is_active": True,
    }

    payload = {
        "reference_location": ref_loc,
        "candidates": [r_normal, r_curated],
        "limit": 2,
        "curation_lists": [curation_list],
    }

    resp = client.post("/api/dining/recommend", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Curated restaurant utility gets boosted to 7.5, raising its ranking to first
    assert data[0]["id"] == "rest-curated"
    assert data[0]["utility_score"] == 7.5
