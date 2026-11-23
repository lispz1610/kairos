"""Contrato HTTP da validação de Backup JSON da Viagem (RF08)."""

from typing import Any

from fastapi.testclient import TestClient

from src.adapters.web.app import app

client = TestClient(app)

BACKUP_VALIDATE_URL = "/api/trip/backup/validate"


def _trip_payload() -> dict[str, Any]:
    """Viagem válida com duas Etapas de Viagem e uma Conexão Interurbana."""
    sp_accommodation = {
        "id": "h-sp",
        "name": "Hospedagem SP",
        "location": [-23.55, -46.66],
    }
    lima_accommodation = {
        "id": "h-lima",
        "name": "Hospedagem Lima",
        "location": [-12.04, -77.03],
    }
    return {
        "id": "trip-sp-lima",
        "title": "São Paulo e Lima",
        "travelers": 2,
        "stages": [
            {
                "id": "stage-sp",
                "city_name": "São Paulo",
                "start_date": "2026-11-01",
                "end_date": "2026-11-03",
                "base_accommodation": sp_accommodation,
                "days": [{"date": "2026-11-01", "base_accommodation": sp_accommodation}],
            },
            {
                "id": "stage-lima",
                "city_name": "Lima",
                "start_date": "2026-11-03",
                "end_date": "2026-11-05",
                "base_accommodation": lima_accommodation,
                "days": [{"date": "2026-11-03", "base_accommodation": lima_accommodation}],
            },
        ],
        "connections": [
            {
                "id": "conn-1",
                "from_stage_id": "stage-sp",
                "to_stage_id": "stage-lima",
                "mode": "flying",
                "modal": "flying",
                "departure_time": "2026-11-03",
                "departure_datetime": "2026-11-03T09:00:00",
                "boarding_cutoff_minutes": 120,
            }
        ],
        "preferences": {"intensities": {"culture": 7}},
        "curation_lists": [],
    }


def test_backup_validate_returns_validated_trip_and_is_idempotent() -> None:
    """Um Backup JSON válido é devolvido normalizado e sobrevive a outro ciclo."""
    response = client.post(BACKUP_VALIDATE_URL, json=_trip_payload())

    assert response.status_code == 200, response.text
    validated = response.json()
    assert validated["id"] == "trip-sp-lima"
    assert validated["title"] == "São Paulo e Lima"
    assert validated["travelers"] == 2
    assert [stage["city_name"] for stage in validated["stages"]] == [
        "São Paulo",
        "Lima",
    ]
    connection = validated["connections"][0]
    assert connection["departure_time"] == "2026-11-03"
    assert connection["departure_datetime"] == "2026-11-03T09:00:00"

    again = client.post(BACKUP_VALIDATE_URL, json=validated)
    assert again.status_code == 200, again.text
    assert again.json() == validated


def test_backup_validate_coerces_values_and_ignores_unknown_fields() -> None:
    """Campos extras são descartados e valores compatíveis são normalizados."""
    payload = _trip_payload()
    payload["travelers"] = "2"
    payload["campo_desconhecido"] = {"legado": True}
    payload["stages"][0]["campo_extra"] = "ignorado"

    response = client.post(BACKUP_VALIDATE_URL, json=payload)

    assert response.status_code == 200, response.text
    validated = response.json()
    assert validated["travelers"] == 2
    assert "campo_desconhecido" not in validated
    assert "campo_extra" not in validated["stages"][0]


def test_backup_validate_rejects_payload_without_required_trip_id() -> None:
    """Um corpo sem a identificação da Viagem recebe 422 com detalhe de schema."""
    response = client.post(BACKUP_VALIDATE_URL, json={"title": "Viagem sem id"})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(
        item["loc"][-1] == "id" and item["type"] == "missing" for item in detail
    )


def test_backup_validate_rejects_incomplete_stage_and_connection() -> None:
    """Etapa sem Hospedagem e Conexão sem partida são recusadas com 422."""
    payload = _trip_payload()
    del payload["stages"][0]["base_accommodation"]
    del payload["connections"][0]["departure_datetime"]
    del payload["connections"][0]["departure_time"]

    response = client.post(BACKUP_VALIDATE_URL, json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(item["loc"][-1] == "base_accommodation" for item in detail)
    assert any(item["loc"][-1] == "departure_datetime" for item in detail)


def test_backup_validate_rejects_invalid_field_types() -> None:
    """Tipos incompatíveis com o schema da Viagem geram 422."""
    payload = _trip_payload()
    payload["travelers"] = "dois"
    payload["stages"] = "não é uma lista de Etapas de Viagem"

    response = client.post(BACKUP_VALIDATE_URL, json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(item["loc"][-1] == "travelers" for item in detail)
    assert any(item["loc"][-1] == "stages" for item in detail)


def test_backup_validate_rejects_non_object_body() -> None:
    """Um JSON que não representa uma Viagem é recusado com detalhe de schema."""
    response = client.post(BACKUP_VALIDATE_URL, json=[1, 2, 3])

    assert response.status_code == 422
    assert response.json()["detail"]
