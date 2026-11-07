from fastapi.testclient import TestClient

from src.adapters.web.app import app

client = TestClient(app)


def test_suggested_curation_endpoint() -> None:
    response = client.get("/api/curation/suggested?city_name=São%20Paulo")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    titles = [item["title"] for item in data]
    assert any("Michelin" in t for t in titles)


def test_places_search_autocomplete_endpoint() -> None:
    response = client.get("/api/places/search?query=Coffee&city_name=São%20Paulo")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert "Coffee" in data[0]["name"] or "Coffee" in data[0]["category"]
