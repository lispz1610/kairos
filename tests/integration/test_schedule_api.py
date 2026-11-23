from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from src.adapters.web.app import app

client = TestClient(app)


def _sample_trip_payload() -> Dict[str, Any]:
    return {
        "id": "trip-sp-lima",
        "title": "SP & Lima",
        "stages": [
            {
                "id": "st-sp",
                "city_name": "São Paulo",
                "start_date": "2026-11-01",
                "end_date": "2026-11-10",
                "base_accommodation": {
                    "id": "h-sp",
                    "name": "Hotel SP",
                    "location": {"latitude": -23.55, "longitude": -46.66},
                },
                "days": [
                    {
                        "date": "2026-11-01",
                        "base_accommodation": {
                            "id": "h-sp",
                            "name": "Hotel SP",
                            "location": {"latitude": -23.55, "longitude": -46.66},
                        },
                    }
                ],
            },
            {
                "id": "st-lima",
                "city_name": "Lima",
                "start_date": "2026-11-10",
                "end_date": "2026-11-15",
                "base_accommodation": {
                    "id": "h-lima",
                    "name": "Hotel Lima",
                    "location": {"latitude": -12.04, "longitude": -77.03},
                },
                "days": [
                    {
                        "date": "2026-11-10",
                        "base_accommodation": {
                            "id": "h-lima",
                            "name": "Hotel Lima",
                            "location": {"latitude": -12.04, "longitude": -77.03},
                        },
                    }
                ],
            },
        ],
        "connections": [
            {
                "id": "conn-1",
                "from_stage_id": "st-sp",
                "to_stage_id": "st-lima",
                "mode": "flying",
                "departure_time": "2026-11-10",
            }
        ],
    }


@pytest.mark.requirement("RF06")
def test_ripple_shift_preview_endpoint() -> None:
    """Verifica a prévia do Deslocamento em Cascata sem alterar a Viagem."""
    trip_payload = _sample_trip_payload()
    resp = client.post(
        "/api/trip/ripple-shift/preview",
        json={"trip": trip_payload, "target_stage_id": "st-sp", "delta_days": 1},
    )
    assert resp.status_code == 200
    preview = resp.json()
    assert preview["delta_days"] == 1
    assert preview["new_target_end"] == "2026-11-11"
    assert len(preview["shifted_stages"]) == 1
    assert preview["shifted_stages"][0]["new_start"] == "2026-11-11"


@pytest.mark.requirement("RF06")
def test_ripple_shift_apply_endpoint() -> None:
    """Verifica o Deslocamento em Cascata nas Etapas e Conexões Interurbanas."""
    trip_payload = _sample_trip_payload()
    resp_apply = client.post(
        "/api/trip/ripple-shift/apply",
        json={"trip": trip_payload, "target_stage_id": "st-sp", "delta_days": 1},
    )
    assert resp_apply.status_code == 200
    updated = resp_apply.json()
    assert updated["stages"][0]["end_date"] == "2026-11-11"
    assert updated["stages"][1]["start_date"] == "2026-11-11"
    assert updated["stages"][1]["end_date"] == "2026-11-16"
    assert updated["connections"][0]["departure_time"] == "2026-11-11"
