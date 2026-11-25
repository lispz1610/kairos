"""Contrato HTTP da validação de Backup JSON da Viagem (RF08)."""

import pytest
from fastapi.testclient import TestClient

from src.adapters.web.app import app
from tests.trip_payloads import restorable_trip_payload

client = TestClient(app)

BACKUP_VALIDATE_URL = "/api/trip/backup/validate"


@pytest.mark.requirement("RF08")
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
    assert connection["mode"] == "flying"

    again = client.post(BACKUP_VALIDATE_URL, json=validated)
    assert again.status_code == 200, again.text
    assert again.json() == validated


@pytest.mark.requirement("RF08", "RF09")
def test_legacy_mode_only_preserves_intercity_modal_and_boarding_margin() -> None:
    """Backup legado com ``mode`` mantém o Modal de Transporte e sua Margem de Embarque."""
    payload = restorable_trip_payload()
    connection = payload["connections"][0]
    del connection["modal"]
    del connection["boarding_cutoff_minutes"]

    response = client.post(BACKUP_VALIDATE_URL, json=payload)

    assert response.status_code == 200, response.text
    normalized = response.json()["connections"][0]
    assert normalized["modal"] == "flying"
    assert normalized["boarding_cutoff_minutes"] == 120


@pytest.mark.requirement("RF08", "RF09")
def test_backup_validate_rejects_unknown_field_in_legacy_connection() -> None:
    """Um campo desconhecido em Conexão Interurbana legada continua gerando 422."""
    payload = restorable_trip_payload()
    connection = payload["connections"][0]
    del connection["modal"]
    connection["campo_obsoleto"] = True

    response = client.post(BACKUP_VALIDATE_URL, json=payload)

    assert response.status_code == 422
    assert any(item["loc"][-1] == "campo_obsoleto" for item in response.json()["detail"])


@pytest.mark.requirement("RF08")
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


@pytest.mark.requirement("RF08")
def test_backup_validate_rejects_payload_without_required_trip_id() -> None:
    """Um corpo sem a identificação da Viagem recebe 422 com detalhe de schema."""
    response = client.post(BACKUP_VALIDATE_URL, json={"title": "Viagem sem id"})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(
        item["loc"][-1] == "id" and item["type"] == "missing" for item in detail
    )


@pytest.mark.requirement("RF08")
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


@pytest.mark.requirement("RF08")
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


@pytest.mark.requirement("RF08")
def test_backup_validate_rejects_empty_identifiers() -> None:
    """Identificadores e nomes vazios herdam do domínio a mesma restrição do Backup."""
    payload = restorable_trip_payload()
    payload["id"] = ""
    payload["title"] = ""
    payload["stages"][0]["city_name"] = ""
    payload["stages"][0]["base_accommodation"]["name"] = ""

    response = client.post(BACKUP_VALIDATE_URL, json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(item["loc"][-1] == "id" for item in detail)
    assert any(item["loc"][-1] == "title" for item in detail)
    assert any(item["loc"][-1] == "city_name" for item in detail)
    assert any(item["loc"][-1] == "name" for item in detail)


@pytest.mark.requirement("RF08")
def test_backup_validate_rejects_non_object_body() -> None:
    """Um JSON que não representa uma Viagem é recusado com detalhe de schema."""
    response = client.post(BACKUP_VALIDATE_URL, json=[1, 2, 3])

    assert response.status_code == 422
    assert response.json()["detail"]


@pytest.mark.requirement("RF14")
def test_backup_validate_preserves_urban_mode_and_defaults_legacy_day() -> None:
    """Backup JSON preserva walking, assume driving quando omitido e recusa flying."""
    payload = restorable_trip_payload()
    payload["stages"][0]["days"][0]["urban_mode"] = "walking"
    payload["stages"][1]["days"][0].pop("urban_mode", None)
    assert "urban_mode" not in payload["stages"][1]["days"][0]

    response = client.post(BACKUP_VALIDATE_URL, json=payload)

    assert response.status_code == 200, response.text
    validated = response.json()
    assert validated["stages"][0]["days"][0]["urban_mode"] == "walking"
    assert validated["stages"][1]["days"][0]["urban_mode"] == "driving"

    invalid = restorable_trip_payload()
    invalid["stages"][0]["days"][0]["urban_mode"] = "flying"
    rejected = client.post(BACKUP_VALIDATE_URL, json=invalid)
    assert rejected.status_code == 422


@pytest.mark.requirement("RF08")
def test_backup_validate_round_trips_itinerary_and_route_stops() -> None:
    """Backup JSON com ItineraryStop e RouteStop valida e sobrevive ao round-trip."""
    payload = restorable_trip_payload()
    poi = {
        "id": "poi-masp",
        "name": "MASP",
        "location": {"latitude": -23.5615, "longitude": -46.6559},
        "window": {"start_time": "10:00:00", "end_time": "18:00:00"},
        "stay_duration_minutes": 60,
        "utility_score": 9.0,
    }
    payload["stages"][0]["days"][0]["itinerary"] = {
        "stops": [
            {
                "poi": poi,
                "arrival_time": "10:00:00",
                "departure_time": "11:00:00",
                "transit_duration_minutes": 10,
            },
            {
                "poi": poi,
                "start": "2026-11-01T14:00:00",
                "duration_minutes": 45,
            },
        ],
        "total_utility": 18.0,
        "total_duration_minutes": 115,
    }

    response = client.post(BACKUP_VALIDATE_URL, json=payload)

    assert response.status_code == 200, response.text
    validated = response.json()
    stops = validated["stages"][0]["days"][0]["itinerary"]["stops"]
    assert stops[0]["arrival_time"] == "10:00:00"
    assert stops[0]["departure_time"] == "11:00:00"
    assert stops[1]["start"] == "2026-11-01T14:00:00"
    assert stops[1]["duration_minutes"] == 45

    again = client.post(BACKUP_VALIDATE_URL, json=validated)
    assert again.status_code == 200, again.text
    assert again.json() == validated


@pytest.mark.requirement("RF08")
@pytest.mark.parametrize("travelers", [0, -1])
def test_backup_validate_rejects_non_positive_travelers(travelers: int) -> None:
    """Viajantes menores que 1 são recusados com HTTP 422."""
    payload = restorable_trip_payload()
    payload["travelers"] = travelers

    response = client.post(BACKUP_VALIDATE_URL, json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(item["loc"][-1] == "travelers" for item in detail)
