from typing import Any, Dict

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


def test_ripple_shift_preview_exposes_old_and_new_dates_for_negative_delta() -> None:
    """Verifica que a prévia negativa informa datas anteriores e recalculadas ao modal."""
    trip_payload = _sample_trip_payload()
    trip_payload["connections"][0].update(
        {
            "departure_datetime": "2026-11-10T09:00:00",
            "modal": "flying",
            "boarding_cutoff_minutes": 120,
        }
    )
    response = client.post(
        "/api/trip/ripple-shift/preview",
        json={"trip": trip_payload, "target_stage_id": "st-sp", "delta_days": -1},
    )
    assert response.status_code == 200
    preview = response.json()
    assert preview["old_target_end"] == "2026-11-10"
    assert preview["new_target_end"] == "2026-11-09"

    shifted_stage = preview["shifted_stages"][0]
    assert shifted_stage["stage_id"] == "st-lima"
    assert (shifted_stage["old_start"], shifted_stage["old_end"]) == ("2026-11-10", "2026-11-15")
    assert (shifted_stage["new_start"], shifted_stage["new_end"]) == ("2026-11-09", "2026-11-14")

    shifted_connection = preview["shifted_connections"][0]
    assert (shifted_connection["old_departure"], shifted_connection["new_departure"]) == (
        "2026-11-10",
        "2026-11-09",
    )


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


def test_ripple_shift_apply_matches_preview_dates_for_positive_delta() -> None:
    """Verifica que a Viagem aplicada reproduz as datas da prévia, inclusive conexões."""
    trip_payload = _sample_trip_payload()
    trip_payload["connections"][0].update(
        {
            "departure_datetime": "2026-11-10T09:00:00",
            "modal": "flying",
            "boarding_cutoff_minutes": 120,
        }
    )
    payload = {"trip": trip_payload, "target_stage_id": "st-sp", "delta_days": 2}
    preview_response = client.post("/api/trip/ripple-shift/preview", json=payload)
    assert preview_response.status_code == 200
    apply_response = client.post("/api/trip/ripple-shift/apply", json=payload)
    assert apply_response.status_code == 200

    preview = preview_response.json()
    applied_trip = apply_response.json()
    assert applied_trip["stages"][0]["end_date"] == preview["new_target_end"] == "2026-11-12"
    assert len(preview["shifted_stages"]) == len(applied_trip["stages"]) - 1
    assert len(preview["shifted_connections"]) == len(applied_trip["connections"])

    for shifted, stage in zip(preview["shifted_stages"], applied_trip["stages"][1:]):
        assert (stage["start_date"], stage["end_date"]) == (
            shifted["new_start"],
            shifted["new_end"],
        )
        assert len(stage["days"]) == shifted["preserved_days_count"]
        assert stage["days"][0]["date"] == shifted["new_start"]

    for shifted, connection in zip(preview["shifted_connections"], applied_trip["connections"]):
        assert connection["departure_time"] == shifted["new_departure"]
        assert connection["departure_datetime"] == shifted["new_departure"] + "T09:00:00"


def test_ripple_shift_apply_rejects_unknown_stage_without_server_state() -> None:
    """Verifica que a rejeição detalha o erro e não deixa Viagem alterada no servidor."""
    trip_payload = _sample_trip_payload()
    rejected = client.post(
        "/api/trip/ripple-shift/apply",
        json={"trip": trip_payload, "target_stage_id": "st-inexistente", "delta_days": 1},
    )
    assert rejected.status_code == 400
    assert "st-inexistente" in rejected.json()["detail"]

    accepted = client.post(
        "/api/trip/ripple-shift/apply",
        json={"trip": trip_payload, "target_stage_id": "st-sp", "delta_days": 1},
    )
    assert accepted.status_code == 200
    assert accepted.json()["stages"][1]["start_date"] == "2026-11-11"


def test_ripple_shift_apply_rejects_shrink_that_eliminates_stage() -> None:
    """Verifica que a aplicação rejeita remover todos os dias de uma Etapa de Viagem."""
    response = client.post(
        "/api/trip/ripple-shift/apply",
        json={"trip": _sample_trip_payload(), "target_stage_id": "st-sp", "delta_days": -10},
    )
    assert response.status_code == 400
    assert "mínimo 1 dia" in response.json()["detail"]
