from fastapi.testclient import TestClient

from src.adapters.web.app import app

client = TestClient(app)


def test_dining_recommend_endpoint() -> None:
    payload = {
        "reference_location": {"latitude": -23.5615, "longitude": -46.6559},
        "candidates": [
            {
                "id": "rest-1",
                "name": "A Baianeira MASP",
                "location": {"latitude": -23.5616, "longitude": -46.6560},
                "category": "restaurant",
                "rating": 4.8,
                "price_tier": "$$",
                "awards": ["Bib Gourmand"],
            },
            {
                "id": "rest-2",
                "name": "Restaurante Longe",
                "location": {"latitude": -23.65, "longitude": -46.75},
                "category": "restaurant",
                "rating": 4.0,
                "price_tier": "$$$$",
            },
        ],
        "limit": 1,
    }

    response = client.post("/api/dining/recommend", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "rest-1"


def test_trip_budget_endpoint() -> None:
    payload = {
        "trip": {
            "id": "trip-sp",
            "title": "SP Trip",
            "stages": [
                {
                    "id": "st-sp",
                    "city_name": "São Paulo",
                    "start_date": "2026-11-01",
                    "end_date": "2026-11-03",
                    "base_accommodation": {
                        "id": "h-1",
                        "name": "Hotel SP",
                        "location": {"latitude": -23.55, "longitude": -46.66},
                        "real_daily_rate": 500.0,
                    },
                    "days": [
                        {
                            "date": "2026-11-01",
                            "base_accommodation": {
                                "id": "h-1",
                                "name": "Hotel SP",
                                "location": {"latitude": -23.55, "longitude": -46.66},
                            },
                        },
                        {
                            "date": "2026-11-02",
                            "base_accommodation": {
                                "id": "h-1",
                                "name": "Hotel SP",
                                "location": {"latitude": -23.55, "longitude": -46.66},
                            },
                        },
                    ],
                }
            ],
            "connections": [],
        },
        "food_profile": "moderate",
    }

    response = client.post("/api/trip/budget", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_accommodation_cost"] == 1000.0  # 2 days * 500
    assert data["total_dining_cost"] == 360.0  # 2 days * 180
    assert data["total_trip_cost"] == 1360.0
