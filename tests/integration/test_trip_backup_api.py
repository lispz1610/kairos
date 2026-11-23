"""Contrato HTTP da validação de Backup JSON da Viagem (RF08)."""

from fastapi.testclient import TestClient

from src.adapters.web.app import app
from tests.trip_payloads import restorable_trip_payload

client = TestClient(app)

BACKUP_VALIDATE_URL = "/api/trip/backup/validate"


def test_backup_validate_returns_validated_trip_and_is_idempotent() -> None:
    """Um Backup JSON válido é devolvido normalizado e sobrevive a outro ciclo."""
    response = client.post(BACKUP_VALIDATE_URL, json=restorable_trip_payload())

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


def test_backup_validate_rejects_unknown_fields_and_untyped_numbers() -> None:
    """Campos desconhecidos e números em texto são recusados com 422 detalhado."""
    payload = restorable_trip_payload()
    payload["travelers"] = "2"
    payload["campo_desconhecido"] = {"legado": True}
    payload["stages"][0]["campo_extra"] = "ignorado"

    response = client.post(BACKUP_VALIDATE_URL, json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(item["loc"][-1] == "travelers" for item in detail)
    assert any(item["loc"][-1] == "campo_desconhecido" for item in detail)
    assert any(item["loc"][-1] == "campo_extra" for item in detail)


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
    payload = restorable_trip_payload()
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
    payload = restorable_trip_payload()
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
