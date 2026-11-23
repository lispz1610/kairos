"""Contrato do perfil condicional do Hypothesis no gate de mutação."""

import os
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parents[1]
CONFTEST = TESTS_DIR / "conftest.py"

_PROFILE_SCRIPT = """
import importlib.util
from hypothesis import settings

before = settings.default.deadline
spec = importlib.util.spec_from_file_location("kairos_conftest", {path!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
after = settings.default.deadline
try:
    registered = settings.get_profile("kairos_sem_prazo").deadline
except Exception:
    registered = "missing"
print(before)
print(after)
print(registered)
"""


def _profile_state(*, mutation: bool) -> tuple[str, str, str]:
    """Importa o conftest em processo isolado e devolve os estados observados."""
    env = os.environ.copy()
    env.pop("HYPOTHESIS_PROFILE", None)
    env.pop("KAIROS_MUTATION", None)
    if mutation:
        env["KAIROS_MUTATION"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", _PROFILE_SCRIPT.format(path=str(CONFTEST))],
        cwd=TESTS_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    before, after, registered = result.stdout.splitlines()
    return before, after, registered


def test_developer_run_keeps_hypothesis_deadline() -> None:
    """Sem a variável de mutação, importar o conftest não altera o prazo nem registra perfil."""
    before, after, registered = _profile_state(mutation=False)
    assert after == before
    assert registered == "missing"


def test_mutation_run_disables_hypothesis_deadline() -> None:
    """No gate de mutação, o perfil dedicado remove apenas o prazo do Hypothesis."""
    _, after, registered = _profile_state(mutation=True)
    assert after == "None"
    assert registered == "None"
