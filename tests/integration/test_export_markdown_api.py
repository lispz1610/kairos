import pytest
from fastapi.testclient import TestClient

from src.adapters.web.app import app

client = TestClient(app)


@pytest.mark.requirement("RF08")
def test_export_markdown_api_endpoint() -> None:
    """Verifica que a exportação Markdown inclui cabeçalho e Quadro Orçamentário."""
    payload = {
        "id": "trip-test",
        "title": "Tour Teste",
        "stages": [
            {
                "id": "st-1",
                "city_name": "Juiz de Fora",
                "start_date": "2026-11-01",
                "end_date": "2026-11-03",
                "base_accommodation": {
                    "id": "h-jf",
                    "name": "Hotel JF",
                    "location": {"latitude": -21.76, "longitude": -43.35},
                },
                "days": [
                    {
                        "date": "2026-11-01",
                        "base_accommodation": {
                            "id": "h-jf",
                            "name": "Hotel JF",
                            "location": {"latitude": -21.76, "longitude": -43.35},
                        },
                    }
                ],
            }
        ],
        "connections": [],
    }

    response = client.post("/api/trip/export-markdown", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "markdown" in data
    assert "# 🌍 Tour Teste" in data["markdown"]
    assert "Quadro Orçamentário" in data["markdown"]
