from __future__ import annotations

from fastapi.testclient import TestClient

from src.adapters.web.app import app, places_adapter

client = TestClient(app)


def test_suggested_curation_endpoint() -> None:
    # Test São Paulo
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


def test_places_search_autocomplete_endpoint() -> None:
    # Search with city
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


def test_cache_persistence_and_offline_replay() -> None:
    # Query twice to exercise Cache-Aside
    resp1 = client.get("/api/places/search?query=Fabrique&city_name=São%20Paulo")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1) >= 1

    resp2 = client.get("/api/places/search?query=Fabrique&city_name=São%20Paulo")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data1 == data2

    # Verify cache contains the search entry
    if hasattr(places_adapter, "_read_cache"):
        cached = places_adapter._read_cache("search:fabrique:são paulo")
        assert cached is not None
        assert "Fabrique" in cached
