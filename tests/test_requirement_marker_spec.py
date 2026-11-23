"""Contrato do marcador ``requirement`` e da anotação do RF03 piloto (#79).

O marcador é registrado na configuração do pytest sem relaxar ``--strict-markers``.
O RF03 (Slots de Refeição e Pausas Experienciais Contextuais) é anotado em casos
representativos das camadas unitária, de integração e de propriedade, e a
convenção aceita um ou mais identificadores ``RFxx`` por caso de teste.
"""

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

from tests.integration import test_dining_api
from tests.property import test_optw_properties
from tests.unit import test_dining_and_budget

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTEST_OPTIONS: dict[str, Any] = tomllib.loads(
    (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
)["tool"]["pytest"]["ini_options"]
SPECIFICATION = (REPO_ROOT / "docs" / "especificacao-requisitos-funcionais.md").read_text(
    encoding="utf-8"
)
CANONICAL_IDS = frozenset(re.findall(r"^### (RF\d{2}) —", SPECIFICATION, re.MULTILINE))

PILOT_CASES = {
    "unit": test_dining_and_budget.test_dining_service_proximity_recommendations,
    "integration": test_dining_api.test_dining_recommend_endpoint,
    "property": test_optw_properties.test_optw_itinerary_never_collides_with_reserved_slots,
}


def _requirement_ids(test: Any) -> tuple[str, ...]:
    """Extrai os identificadores do marcador ``requirement`` de um caso de teste."""
    identifiers: list[str] = []
    for mark in getattr(test, "pytestmark", ()):
        if mark.name == "requirement":
            identifiers.extend(str(arg) for arg in mark.args)
    return tuple(identifiers)


def test_marker_registered_and_strict_markers_active(pytestconfig: pytest.Config) -> None:
    """O marcador está registrado e ``--strict-markers`` permanece ativo."""
    assert any(str(entry).startswith("requirement:") for entry in PYTEST_OPTIONS["markers"])
    assert "--strict-markers" in PYTEST_OPTIONS["addopts"]
    assert pytestconfig.getoption("strict_markers") is True


def test_pilot_ids_follow_canonical_rfxx_spelling() -> None:
    """Os identificadores anotados seguem a grafia RFxx da especificação."""
    assert CANONICAL_IDS >= {f"RF{number:02d}" for number in range(1, 14)}
    for test in PILOT_CASES.values():
        identifiers = _requirement_ids(test)
        assert identifiers
        assert all(re.fullmatch(r"RF\d{2}", identifier) for identifier in identifiers)
        assert set(identifiers) <= CANONICAL_IDS


def test_pilot_requirement_rf03_annotated_in_all_three_layers() -> None:
    """O mesmo RF03 está anotado nas camadas unitária, integração e propriedade."""
    assert set(PILOT_CASES) == {"unit", "integration", "property"}
    for layer, test in PILOT_CASES.items():
        assert "RF03" in _requirement_ids(test), layer


def test_convention_accepts_multiple_identifiers_in_one_marker() -> None:
    """Um único marcador ``requirement`` aceita mais de um identificador RFxx."""
    case = test_optw_properties.test_optw_itinerary_never_collides_with_reserved_slots
    marks = [mark for mark in case.pytestmark if mark.name == "requirement"]
    assert len(marks) == 1
    assert marks[0].args == ("RF03", "RF04")


def test_annotation_preserves_existing_test_contracts() -> None:
    """A anotação preserva o nome e a documentação dos casos de teste existentes."""
    expected_names = {
        "unit": "test_dining_service_proximity_recommendations",
        "integration": "test_dining_recommend_endpoint",
        "property": "test_optw_itinerary_never_collides_with_reserved_slots",
    }
    modules = {
        "unit": test_dining_and_budget,
        "integration": test_dining_api,
        "property": test_optw_properties,
    }
    for layer, name in expected_names.items():
        case = PILOT_CASES[layer]
        assert case.__name__ == name
        assert case.__doc__
        assert getattr(modules[layer], name) is case
