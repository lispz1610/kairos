"""Testes unitários dos modelos temporais de ``InterCityConnection`` (#34).

Cobre os contratos de #34: ``InterCityConnection`` define ``departure_datetime:
datetime`` obrigatório e ``boarding_cutoff_minutes`` (Margem de Embarque) com
padrão por Modal de Transporte; ``TimeWindow``, ``POI``, ``RouteStop`` e
``Itinerary`` compõem o modelo temporal do Dia de Viagem.
"""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from src.core.domain.models import (
    InterCityConnection,
    TransportMode,
)

DEPARTURE_DATETIME = datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc)


def test_intercityconnection_requires_departure_datetime():
    """Garante que departure_datetime é obrigatório para InterCityConnection."""
    with pytest.raises(ValidationError):
        InterCityConnection(origin="A", destination="B", modal="flying")


@pytest.mark.parametrize(
    ("modal", "expected_cutoff"),
    [
        (TransportMode.FLYING, 120),
        (TransportMode.DRIVING, 30),
        (TransportMode.TRANSIT, 30),
        ("flying", 120),
        ("driving", 30),
        ("transit", 30),
        ("ferry", 30),
    ],
)
def test_intercityconnection_defaults_boarding_cutoff_per_modal(modal, expected_cutoff):
    """Valida o valor default de margem de embarque por modal."""
    connection = InterCityConnection(
        origin="A",
        destination="B",
        modal=modal,
        departure_datetime=DEPARTURE_DATETIME,
    )

    assert connection.boarding_cutoff_minutes == expected_cutoff


def test_intercityconnection_defaults_boarding_cutoff_when_modal_omitted_or_none():
    """Garante fallback de margem de embarque quando modal é omitido ou None."""
    connection = InterCityConnection(departure_datetime=DEPARTURE_DATETIME)

    assert connection.boarding_cutoff_minutes == 30
    assert InterCityConnection._resolve_boarding_cutoff(None) == 30
    assert InterCityConnection._resolve_boarding_cutoff("") == 30
    assert InterCityConnection._resolve_boarding_cutoff("unknown") == 30
    assert InterCityConnection._resolve_boarding_cutoff(TransportMode.FLYING) == 120
    assert InterCityConnection._resolve_boarding_cutoff("flying") == 120


def test_intercityconnection_respects_explicit_boarding_cutoff():
    """Verifica que a margem de embarque explícita é respeitada."""
    connection = InterCityConnection(
        origin="A",
        destination="B",
        modal="flying",
        departure_datetime=DEPARTURE_DATETIME,
        boarding_cutoff_minutes=45,
    )

    assert connection.boarding_cutoff_minutes == 45


@pytest.mark.parametrize(
    ("raw_departure", "expected"),
    [
        (datetime(2026, 11, 20, 0, 0), datetime(2026, 11, 20, 0, 0)),
        (date(2026, 11, 20), datetime(2026, 11, 20, 0, 0)),
        ("2026-11-20T00:00:00", datetime(2026, 11, 20, 0, 0)),
        ("2026-11-20", datetime(2026, 11, 20, 0, 0)),
    ],
)
def test_intercityconnection_normalizes_legacy_departure_time(raw_departure, expected):
    """Garante normalização de departure_time legado (datetime, date e ISO str)."""
    connection = InterCityConnection(departure_time=raw_departure)

    assert connection.departure_datetime == expected
    assert connection.effective_departure_time == date(2026, 11, 20)


def test_intercityconnection_rejects_non_dict_input_and_defaults_unknown_modal():
    """Garante retorno inalterado para entrada não-dict e fallback de modal desconhecido."""
    with pytest.raises(ValidationError):
        InterCityConnection.model_validate("invalid-payload")

    connection = InterCityConnection(
        departure_datetime=DEPARTURE_DATETIME,
        modal="ferry",
        boarding_cutoff_minutes=None,
    )
    assert connection.boarding_cutoff_minutes == 30
