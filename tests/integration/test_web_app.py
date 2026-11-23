import pytest
from fastapi.testclient import TestClient

from src.adapters.web.app import app

client = TestClient(app)


@pytest.mark.requirement("RF08")
def test_health_check() -> None:
    """Verifica que o endpoint de saúde responde com o status da aplicação."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "kairos"}


@pytest.mark.requirement("RF08")
def test_index_page_renders_html() -> None:
    """Verifica que a página inicial renderiza o HTML da aplicação."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Kairos — Traçador Dinâmico de Rotas Turísticas" in response.text
    assert "kairos_trip_state_v1" in response.text
    assert "leaflet" in response.text.lower()
