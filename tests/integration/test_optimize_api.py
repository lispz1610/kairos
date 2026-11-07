from fastapi.testclient import TestClient

from src.adapters.web.app import app

client = TestClient(app)


def test_optimize_endpoint_returns_valid_itinerary() -> None:
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
