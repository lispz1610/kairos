"""Testes de integração de ``POST /api/trip/replan`` (ticket #38).

Cada teste é uma asserção lógica sobre a interface pública do endpoint:
dado o Roteiro de um Dia de Viagem, um horário atual e os Eventos de
Contingência (``ContingencyEventRequest``) aplicados, a resposta devolve o
Roteiro replanejado com os metadados de impacto — ``preserved_pois``,
``removed_pois`` e ``intercity_risk_alert``.
"""

from datetime import datetime, time
from typing import Any

from fastapi.testclient import TestClient

from src.adapters.web.app import app
from src.core.domain.models import (
    POI,
    InterCityConnection,
    Itinerary,
    RouteStop,
    TimeWindow,
)

client = TestClient(app)


def _poi(poi_id, opening, closing, utility_score=5.0):
    """Construtor de POIs com Janela de Funcionamento ``[opening, closing]``."""
    return POI(
        id=poi_id,
        name=f"Ponto de Interesse {poi_id}",
        coordinates=(-23.5505, -46.6333),
        operating_window=TimeWindow(start=opening, end=closing),
        utility_score=utility_score,
    )


def _stop(poi, start, duration_minutes=30):
    """Visita ao POI: ``start`` e Tempo de Permanência em minutos."""
    return RouteStop(poi=poi, start=start, duration_minutes=duration_minutes)


def _payload(
    day, current_time, availability_window, events, **overrides
) -> dict[str, Any]:
    """Corpo da requisição de ``POST /api/trip/replan`` — ``events`` no
    formato ``ContingencyEventRequest``."""
    payload = {
        "day_id": "dia-2026-11-20",
        "itinerary": day.model_dump(mode="json"),
        "current_time": current_time.isoformat(),
        "availability_window": availability_window.model_dump(mode="json"),
        "current_coordinate": [-23.5505, -46.6333],
        "events": events,
        "closed_pois": [],
        "skipped_pois": [],
        "intercity_connection": None,
        "travel_time_minutes": 15.0,
    }
    payload.update(overrides)
    return payload


def test_delay_event_replan_keeps_route_starting_after_the_delayed_time() -> None:
    availability_window = TimeWindow(start=time(8, 0), end=time(20, 0))
    poi_a = _poi("POI-A", time(9, 0), time(12, 0), utility_score=9.0)
    poi_b = _poi("POI-B", time(9, 0), time(12, 0), utility_score=8.0)
    day = Itinerary(
        stops=[
            _stop(poi_a, datetime(2026, 11, 20, 9, 0), 30),
            _stop(poi_b, datetime(2026, 11, 20, 9, 10), 30),
        ]
    )
    events = [{"type": "delay", "delay_minutes": 20}]

    response = client.post(
        "/api/trip/replan",
        json=_payload(day, datetime(2026, 11, 20, 9, 0), availability_window, events),
    )

    data = response.json()
    assert data["preserved_pois"] == ["POI-A", "POI-B"]
    assert [stop["poi"]["id"] for stop in data["itinerary"]] == ["POI-A", "POI-B"]
    assert data["itinerary"][1]["start"] == "2026-11-20T09:10:00"
    assert data["removed_pois"] == []
    assert data["intercity_risk_alert"] is None


def test_closure_event_replan_excludes_the_closed_poi() -> None:
    availability_window = TimeWindow(start=time(8, 0), end=time(20, 0))
    poi_a = _poi("POI-A", time(8, 0), time(10, 0), utility_score=9.0)
    poi_b = _poi("POI-B", time(8, 0), time(11, 0), utility_score=8.0)
    poi_c = _poi("POI-C", time(9, 0), time(12, 0), utility_score=7.0)
    day = Itinerary(
        stops=[
            _stop(poi_a, datetime(2026, 11, 20, 9, 0), 30),
            _stop(poi_b, datetime(2026, 11, 20, 9, 30), 30),
            _stop(poi_c, datetime(2026, 11, 20, 10, 30), 30),
        ]
    )
    events = [{"type": "closure", "poi_id": "POI-B"}]

    response = client.post(
        "/api/trip/replan",
        json=_payload(day, datetime(2026, 11, 20, 8, 45), availability_window, events),
    )

    data = response.json()
    assert [stop["poi"]["id"] for stop in data["itinerary"]] == ["POI-A", "POI-C"]
    assert data["removed_pois"] == ["POI-B"]
    assert data["preserved_pois"] == []
    assert data["intercity_risk_alert"] is None


def test_skip_stop_event_replan_excludes_the_skipped_poi() -> None:
    availability_window = TimeWindow(start=time(8, 0), end=time(20, 0))
    poi_a = _poi("POI-A", time(8, 0), time(10, 0), utility_score=9.0)
    poi_b = _poi("POI-B", time(8, 0), time(11, 0), utility_score=8.0)
    poi_c = _poi("POI-C", time(9, 0), time(12, 0), utility_score=7.0)
    day = Itinerary(
        stops=[
            _stop(poi_a, datetime(2026, 11, 20, 9, 0), 30),
            _stop(poi_b, datetime(2026, 11, 20, 9, 30), 30),
            _stop(poi_c, datetime(2026, 11, 20, 10, 30), 30),
        ]
    )
    events = [{"type": "skip", "poi_id": "POI-B"}]

    response = client.post(
        "/api/trip/replan",
        json=_payload(day, datetime(2026, 11, 20, 8, 45), availability_window, events),
    )

    data = response.json()
    assert [stop["poi"]["id"] for stop in data["itinerary"]] == ["POI-A", "POI-C"]
    assert data["removed_pois"] == ["POI-B"]


def test_duration_adjustment_event_replan_applies_the_new_duration() -> None:
    availability_window = TimeWindow(start=time(8, 0), end=time(20, 0))
    poi_a = _poi("POI-A", time(8, 0), time(12, 0), utility_score=9.0)
    poi_b = _poi("POI-B", time(8, 0), time(12, 0), utility_score=8.0)
    day = Itinerary(
        stops=[
            _stop(poi_a, datetime(2026, 11, 20, 9, 0), 30),
            _stop(poi_b, datetime(2026, 11, 20, 10, 0), 30),
        ]
    )
    events = [
        {"type": "duration_adjustment", "poi_id": "POI-A", "new_duration_minutes": 60}
    ]

    response = client.post(
        "/api/trip/replan",
        json=_payload(day, datetime(2026, 11, 20, 9, 0), availability_window, events),
    )

    data = response.json()
    assert [stop["poi"]["id"] for stop in data["itinerary"]] == ["POI-A", "POI-B"]
    assert data["itinerary"][0]["duration_minutes"] == 60
    assert data["preserved_pois"] == ["POI-A"]


def test_reserved_future_stops_are_preserved() -> None:
    availability_window = TimeWindow(start=time(8, 0), end=time(20, 0))
    poi_a = _poi("POI-A", time(9, 0), time(12, 0), utility_score=9.0)
    poi_c = _poi("POI-C", time(11, 0), time(12, 0), utility_score=7.0)
    day = Itinerary(stops=[_stop(poi_a, datetime(2026, 11, 20, 9, 0), 30)])
    reserved_stop = _stop(poi_c, datetime(2026, 11, 20, 11, 0), 30)

    response = client.post(
        "/api/trip/replan",
        json=_payload(
            day,
            datetime(2026, 11, 20, 9, 0),
            availability_window,
            [],
            reserved_future_stops=[reserved_stop.model_dump(mode="json")],
        ),
    )

    data = response.json()
    assert [stop["poi"]["id"] for stop in data["itinerary"]] == ["POI-A", "POI-C"]
    assert data["preserved_pois"] == ["POI-A", "POI-C"]
    assert data["itinerary"][1]["start"] == "2026-11-20T11:00:00"
    assert data["itinerary"][1]["duration_minutes"] == 30


def test_intercity_risk_alert_reported_when_boarding_does_not_fit():
    availability_window = TimeWindow(start=time(8, 0), end=time(18, 0))
    poi_a = _poi("POI-A", time(14, 0), time(18, 0), utility_score=9.0)
    connection = InterCityConnection(
        origin="A",
        destination="B",
        departure_datetime=datetime(2026, 11, 20, 15, 0),
        boarding_cutoff_minutes=30,
    )
    day = Itinerary(stops=[_stop(poi_a, datetime(2026, 11, 20, 14, 0), 30)])

    response = client.post(
        "/api/trip/replan",
        json=_payload(
            day,
            datetime(2026, 11, 20, 14, 45),
            availability_window,
            [],
            intercity_connection=connection.model_dump(mode="json"),
        ),
    )

    data = response.json()
    assert data["intercity_risk_alert"] == {"deficit_minutes": 15}
    assert data["preserved_pois"] == ["POI-A"]
