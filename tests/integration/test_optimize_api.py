import pytest
from fastapi.testclient import TestClient

from src.adapters.web.app import app

client = TestClient(app)

_RF14_PAYLOAD: dict[str, object] = {
    "start_location": {"latitude": 0.0, "longitude": 0.0},
    "end_location": {"latitude": 0.0, "longitude": 0.0},
    "window": {"start_time": "09:00:00", "end_time": "23:59:00"},
    "candidates": [
        {
            "id": "poi-um-grau",
            "name": "POI a um grau de latitude",
            "location": {"latitude": 1.0, "longitude": 0.0},
            "window": {"start_time": "00:00:00", "end_time": "23:59:00"},
            "stay_duration_minutes": 30,
            "utility_score": 10.0,
        }
    ],
}


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


@pytest.mark.requirement("RF14")
def test_optimize_omitted_and_driving_modal_have_same_25_kmh_displacement() -> None:
    """Verifica que omissão e driving produzem o mesmo Deslocamento, a 25 km/h."""
    default_response = client.post("/api/trip/optimize", json=_RF14_PAYLOAD)
    driving_response = client.post(
        "/api/trip/optimize", json={**_RF14_PAYLOAD, "urban_mode": "driving"}
    )

    assert default_response.status_code == 200
    assert driving_response.status_code == 200
    default_displacement = [
        stop["transit_duration_minutes"] for stop in default_response.json()["stops"]
    ]
    driving_displacement = [
        stop["transit_duration_minutes"] for stop in driving_response.json()["stops"]
    ]
    assert default_displacement == driving_displacement == [267]


@pytest.mark.requirement("RF14")
def test_optimize_accepts_walking_urban_modal() -> None:
    """Verifica que walking é aceito como Modal Urbano no pedido de otimização."""
    response = client.post(
        "/api/trip/optimize", json={**_RF14_PAYLOAD, "urban_mode": "walking"}
    )
    assert response.status_code == 200
    assert len(response.json()["stops"]) == 1


@pytest.mark.requirement("RF14")
@pytest.mark.parametrize("non_urban_mode", ["flying", "transit"])
def test_optimize_rejects_flying_and_transit(non_urban_mode: str) -> None:
    """Verifica que flying e transit são recusados, sem coerção para driving."""
    response = client.post(
        "/api/trip/optimize", json={**_RF14_PAYLOAD, "urban_mode": non_urban_mode}
    )
    assert response.status_code == 422
