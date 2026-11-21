"""Testes unitários dos eventos de contingência (ticket #35).

Cada teste é uma asserção lógica sobre a interface pública dos eventos:
construtores, campos e serialização (``model_dump`` / ``model_dump_json``).
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.core.domain.events import (
    ClosureEvent,
    DelayEvent,
    DurationAdjustmentEvent,
    SkipStopEvent,
)

NOW = datetime(2026, 11, 19, 8, 30, tzinfo=timezone.utc)


def test_delay_event_fields():
    """Valida os campos de DelayEvent."""
    event = DelayEvent(delay_minutes=15, current_time=NOW, coordinates=(-23.5, -46.6))

    assert (event.delay_minutes, event.current_time, event.coordinates) == (
        15,
        NOW,
        (-23.5, -46.6),
    )


def test_delay_event_serializes_to_expected_dict():
    """Valida a serialização para dicionário de DelayEvent."""
    event = DelayEvent(delay_minutes=15, current_time=NOW, coordinates=(-23.5, -46.6))

    assert event.model_dump() == {
        "delay_minutes": 15,
        "current_time": NOW,
        "coordinates": (-23.5, -46.6),
    }


def test_delay_event_round_trips_serialization():
    """Valida o round-trip de serialização JSON de DelayEvent."""
    event = DelayEvent(delay_minutes=15, current_time=NOW, coordinates=(-23.5, -46.6))

    assert DelayEvent.model_validate_json(event.model_dump_json()) == event


def test_delay_event_rejects_negative_delay_minutes():
    """Valida rejeição de delay negativo em DelayEvent."""
    with pytest.raises(ValidationError):
        DelayEvent(delay_minutes=-5, current_time=NOW, coordinates=(-23.5, -46.6))


def test_closure_event_identifies_closed_poi():
    """Valida identificação do POI fechado em ClosureEvent."""
    event = ClosureEvent(poi_id="POI-001")

    assert event.poi_id == "POI-001"


def test_closure_event_rejects_empty_poi_id():
    """Valida rejeição de ID vazio em ClosureEvent."""
    with pytest.raises(ValidationError):
        ClosureEvent(poi_id="")


def test_skip_stop_event_identifies_skipped_poi():
    """Valida identificação do POI pulado em SkipStopEvent."""
    event = SkipStopEvent(poi_id="POI-002")

    assert event.poi_id == "POI-002"


def test_skip_stop_event_rejects_empty_poi_id():
    """Valida rejeição de ID vazio em SkipStopEvent."""
    with pytest.raises(ValidationError):
        SkipStopEvent(poi_id="")


def test_duration_adjustment_event_targets_poi_with_new_duration():
    """Valida campos de DurationAdjustmentEvent."""
    event = DurationAdjustmentEvent(poi_id="POI-003", new_duration_minutes=90)

    assert (event.poi_id, event.new_duration_minutes) == ("POI-003", 90)


def test_duration_adjustment_event_rejects_negative_duration():
    """Valida rejeição de duração negativa em DurationAdjustmentEvent."""
    with pytest.raises(ValidationError):
        DurationAdjustmentEvent(poi_id="POI-003", new_duration_minutes=-1)
