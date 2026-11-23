import pytest
from fastapi.testclient import TestClient

from src.adapters.web.app import app

client = TestClient(app)


def test_optimize_endpoint_returns_valid_itinerary() -> None:
    """Verifica que o endpoint retorna um Roteiro válido dentro da Janela de Disponibilidade."""
    payload = {
        "start_location": {"latitude": -23.5505, "longitude": -46.6333},
        "end_location": {"latitude": -23.5600, "longitude": -46.6500},
        "window": {"start_time": "09:00:00", "end_time": "18:00:00"},
        "candidates": [
            {
                "id": "poi-masp",
                "name": "MASP",
                "location": {"latitude": -23.5615, "longitude": -46.6559},
                "window": {"start_time": "10:00:00", "end_time": "18:00:00"},
                "stay_duration_minutes": 120,
                "utility_score": 10.0,
            },
            {
                "id": "poi-park",
                "name": "Parque Ibirapuera",
                "location": {"latitude": -23.5874, "longitude": -46.6576},
                "window": {"start_time": "08:00:00", "end_time": "20:00:00"},
                "stay_duration_minutes": 90,
                "utility_score": 8.0,
            },
        ],
    }

    response = client.post("/api/trip/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "stops" in data
    assert "total_utility" in data
    assert len(data["stops"]) >= 1
    assert data["total_utility"] >= 10.0


@pytest.mark.requirement("RF03")
def test_optimize_endpoint_respects_reserved_slots() -> None:
    """Verifica que o Roteiro gerado não colide com Slots de Refeição reservados."""
    payload = {
        "start_location": {"latitude": -23.5505, "longitude": -46.6333},
        "end_location": {"latitude": -23.5600, "longitude": -46.6500},
        "window": {"start_time": "09:00:00", "end_time": "21:30:00"},
        "reserved_slots": [
            {"start_time": "12:30:00", "end_time": "14:00:00"},
            {"start_time": "15:30:00", "end_time": "16:15:00"},
            {"start_time": "18:00:00", "end_time": "19:15:00"},
            {"start_time": "19:30:00", "end_time": "21:00:00"},
        ],
        "candidates": [
            {
                "id": f"poi-{i}",
                "name": f"Atração {i}",
                "location": {
                    "latitude": -23.5510 - (i * 0.005),
                    "longitude": -46.6350 - (i * 0.005),
                },
                "window": {"start_time": "09:00:00", "end_time": "21:00:00"},
                "stay_duration_minutes": 60,
                "utility_score": 5.0 + i,
            }
            for i in range(5)
        ],
    }

    response = client.post("/api/trip/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["stops"]) >= 2

    # Verifica ausência de colisão com qualquer slot reservado
    reserved = [
        ("12:30:00", "14:00:00"),
        ("15:30:00", "16:15:00"),
        ("18:00:00", "19:15:00"),
        ("19:30:00", "21:00:00"),
    ]
    for stop in data["stops"]:
        arr = stop["arrival_time"]
        dep = stop["departure_time"]
        for r_start, r_end in reserved:
            overlap = max(arr, r_start) < min(dep, r_end)
            assert not overlap, (
                f"Stop {stop['poi']['name']} colidiu com slot reservado {r_start}-{r_end}"
            )
