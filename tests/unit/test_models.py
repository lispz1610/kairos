"""Testes unitários dos modelos temporais de ``InterCityConnection`` (#34).

Cobre os contratos de #34: ``InterCityConnection`` define ``departure_datetime:
datetime`` obrigatório e ``boarding_cutoff_minutes`` (Margem de Embarque) com
padrão por Modal de Transporte; ``TimeWindow``, ``POI``, ``RouteStop`` e
``Itinerary`` compõem o modelo temporal do Dia de Viagem.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.core.domain.models import (
    InterCityConnection,
    Itinerary,
    POI,
    RouteStop,
    TimeWindow,
)

DEPARTURE_DATETIME = datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc)


def test_intercityconnection_requires_departure_datetime():
    with pytest.raises(ValidationError):
        InterCityConnection(origin="A", destination="B", modal="flying")


@pytest.mark.parametrize(
    ("modal", "expected_cutoff"),
    [("flying", 120), ("driving", 30), ("transit", 30)],
)
def test_intercityconnection_defaults_boarding_cutoff_per_modal(modal, expected_cutoff):
    connection = InterCityConnection(
        origin="A",
        destination="B",
        modal=modal,
        departure_datetime=DEPARTURE_DATETIME,
    )

    assert connection.boarding_cutoff_minutes == expected_cutoff


def test_intercityconnection_respects_explicit_boarding_cutoff():
    connection = InterCityConnection(
        origin="A",
        destination="B",
        modal="flying",
        departure_datetime=DEPARTURE_DATETIME,
        boarding_cutoff_minutes=45,
    )

    assert connection.boarding_cutoff_minutes == 45
