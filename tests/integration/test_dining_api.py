import pytest
from fastapi.testclient import TestClient

from src.adapters.web.app import app

client = TestClient(app)


@pytest.mark.requirement("RF03")
def test_dining_recommend_endpoint() -> None:
    """Verifica que o endpoint prioriza o restaurante próximo e bem avaliado."""
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


@pytest.mark.requirement("RF07")
def test_trip_budget_endpoint() -> None:
    """Verifica a Estimativa de Gastos consolidada de hospedagem e alimentação da Viagem."""
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


@pytest.mark.requirement("RF07")
def test_trip_budget_endpoint_with_custom_food_profile_and_multiple_travelers() -> None:
    """Verifica a Estimativa de Gastos por perfil alimentar e número de viajantes."""
    payload = {
        "trip": {
            "id": "trip-sp-group",
            "title": "SP Group Trip",
            "travelers": 3,
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
                        "real_daily_rate": 600.0,
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
        "food_profile": "fine_dining",
    }

    response = client.post("/api/trip/budget", json=payload)
    assert response.status_code == 200
    data = response.json()
    # 2 nights at 600.0 per room = 1200.0
    assert data["total_accommodation_cost"] == 1200.0
    # Fine dining = 400.0 * 2 days * 3 travelers = 2400.0
    assert data["total_dining_cost"] == 2400.0
    assert data["total_trip_cost"] == 3600.0
    assert data["stage_breakdowns"]["st-sp"]["total_cost"] == 3600.0


@pytest.mark.requirement("RF03", "RF04")
def test_contextual_dining_slots_endpoint() -> None:
    """Verifica os Slots de Refeição contextuais e as recomendações por Ponto de Interesse."""
    dep_hotel_loc = {"latitude": -23.5500, "longitude": -46.6300}
    ret_hotel_loc = {"latitude": -23.5700, "longitude": -46.6700}

    # Itinerário com um POI de manhã e outro à tarde
    itinerary = {
        "stops": [
            {
                "poi": {
                    "id": "poi-masp",
                    "name": "MASP",
                    "location": {"latitude": -23.5615, "longitude": -46.6559},
                    "stay_duration_minutes": 90,
                },
                "arrival_time": "10:00:00",
                "departure_time": "11:30:00",
                "transit_duration_minutes": 15,
            },
            {
                "poi": {
                    "id": "poi-park",
                    "name": "Parque Ibirapuera",
                    "location": {"latitude": -23.5874, "longitude": -46.6576},
                    "stay_duration_minutes": 90,
                },
                "arrival_time": "14:30:00",
                "departure_time": "16:00:00",
                "transit_duration_minutes": 20,
            },
        ],
        "total_utility": 15.0,
        "total_duration_minutes": 360,
    }

    # Candidatos a restaurante: um perto do MASP, um perto do Ibirapuera
    candidates = [
        {
            "id": "rest-near-masp",
            "name": "Bistrô do MASP",
            "location": {"latitude": -23.5616, "longitude": -46.6560},
            "category": "restaurant",
            "rating": 4.8,
            "price_tier": "$$",
            "awards": ["Bib Gourmand"],
        },
        {
            "id": "rest-near-park",
            "name": "Gourmet Ibirapuera",
            "location": {"latitude": -23.5875, "longitude": -46.6577},
            "category": "restaurant",
            "rating": 4.9,
            "price_tier": "$$$$",
            "awards": ["1 Estrela Michelin"],
        },
        {
            "id": "cafe-near-park",
            "name": "Café do Parque",
            "location": {"latitude": -23.5870, "longitude": -46.6570},
            "category": "cafe",
            "rating": 4.7,
            "price_tier": "$",
        },
    ]

    payload = {
        "departure_location": dep_hotel_loc,
        "return_location": ret_hotel_loc,
        "restaurant_candidates": candidates,
        "itinerary": itinerary,
        "preferences": {
            "intensities": {
                "Coffee Lover": 8.0,
                "Wine Lover": 2.0,
            }
        },
    }

    response = client.post("/api/dining/contextual-slots", json=payload)
    assert response.status_code == 200
    slots = response.json()

    slot_ids = [s["id"] for s in slots]
    assert "slot-lunch" in slot_ids
    assert "slot-coffee" in slot_ids
    assert "slot-dinner" in slot_ids
    assert "slot-wine" not in slot_ids  # Wine Lover < 5

    lunch_slot = next(s for s in slots if s["id"] == "slot-lunch")
    dinner_slot = next(s for s in slots if s["id"] == "slot-dinner")

    # Almoço deve recomendar primeiro o bistrô próximo ao MASP (último POI da manhã)
    assert lunch_slot["recommended_places"][0]["id"] == "rest-near-masp"

    # Jantar deve recomendar primeiro o gourmet próximo ao Ibirapuera (último POI da tarde)
    assert dinner_slot["recommended_places"][0]["id"] == "rest-near-park"


@pytest.mark.requirement("RF03", "RF04")
def test_contextual_dining_slots_includes_thematic_slots_at_intensity_five() -> None:
    """Verifica a fronteira inclusiva de intensidade dos Slots temáticos de Café e Vinho."""
    payload = {
        "departure_location": {"latitude": -23.55, "longitude": -46.63},
        "return_location": {"latitude": -23.57, "longitude": -46.67},
        "restaurant_candidates": [
            {
                "id": "rest-central",
                "name": "Restaurante Central",
                "location": {"latitude": -23.56, "longitude": -46.65},
                "category": "restaurant",
            }
        ],
        "preferences": {
            "intensities": {
                "Coffee Lover": 5.0,
                "Wine Lover": 5.0,
            }
        },
    }

    response = client.post("/api/dining/contextual-slots", json=payload)
    assert response.status_code == 200
    slot_ids = [slot["id"] for slot in response.json()]
    assert "slot-coffee" in slot_ids
    assert "slot-wine" in slot_ids
