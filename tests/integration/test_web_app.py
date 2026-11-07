from fastapi.testclient import TestClient

from src.adapters.web.app import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "kairos"}


def test_index_page_renders_html() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Kairos — Traçador Dinâmico de Rotas Turísticas" in response.text
    assert "kairos_trip_state_v1" in response.text
    assert "leaflet" in response.text.lower()
