"""Construtores compartilhados de payloads de Viagem para contratos HTTP."""

from copy import deepcopy
from typing import Any


def accommodation_payload(
    id: str, name: str, latitude: float, longitude: float, *, as_list: bool = False
) -> dict[str, Any]:
    """Monta uma Hospedagem com coordenadas em objeto ou em tupla JSON."""
    location: Any = (
        [latitude, longitude]
        if as_list
        else {"latitude": latitude, "longitude": longitude}
    )
    return {"id": id, "name": name, "location": location}


def stage_payload(
    *,
    stage_id: str,
    city_name: str,
    start_date: str,
    end_date: str,
    accommodation: dict[str, Any],
) -> dict[str, Any]:
    """Monta uma Etapa de Viagem com um Dia de Viagem inicial."""
    return {
        "id": stage_id,
        "city_name": city_name,
        "start_date": start_date,
        "end_date": end_date,
        "base_accommodation": deepcopy(accommodation),
        "days": [{"date": start_date, "base_accommodation": deepcopy(accommodation)}],
    }


def intercity_connection_payload(
    *, from_stage_id: str, to_stage_id: str, departure_date: str
) -> dict[str, Any]:
    """Monta uma Conexão Interurbana com partida legada (apenas data)."""
    return {
        "id": "conn-1",
        "from_stage_id": from_stage_id,
        "to_stage_id": to_stage_id,
        "mode": "flying",
        "departure_time": departure_date,
    }


def with_departure_datetime(payload: dict[str, Any]) -> dict[str, Any]:
    """Devolve uma cópia da Viagem com data, hora e Margem de Embarque na Conexão."""
    updated = deepcopy(payload)
    connection = updated["connections"][0]
    departure = str(connection["departure_time"])
    connection.update(
        {
            "departure_datetime": departure + "T09:00:00",
            "modal": "flying",
            "boarding_cutoff_minutes": 120,
        }
    )
    return updated


def restorable_trip_payload() -> dict[str, Any]:
    """Viagem válida usada como Backup JSON no contrato de restauração."""
    sp_accommodation = accommodation_payload(
        "h-sp", "Hospedagem SP", -23.55, -46.66, as_list=True
    )
    lima_accommodation = accommodation_payload(
        "h-lima", "Hospedagem Lima", -12.04, -77.03, as_list=True
    )
    trip = {
        "id": "trip-sp-lima",
        "title": "São Paulo e Lima",
        "travelers": 2,
        "stages": [
            stage_payload(
                stage_id="stage-sp",
                city_name="São Paulo",
                start_date="2026-11-01",
                end_date="2026-11-03",
                accommodation=sp_accommodation,
            ),
            stage_payload(
                stage_id="stage-lima",
                city_name="Lima",
                start_date="2026-11-03",
                end_date="2026-11-05",
                accommodation=lima_accommodation,
            ),
        ],
        "connections": [
            intercity_connection_payload(
                from_stage_id="stage-sp",
                to_stage_id="stage-lima",
                departure_date="2026-11-03",
            )
        ],
        "preferences": {"intensities": {"culture": 7}},
        "curation_lists": [],
    }
    return with_departure_datetime(trip)
