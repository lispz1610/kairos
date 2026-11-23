"""Contrato do perfil condicional do Hypothesis no gate de mutação."""

import os
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parents[1]


def _default_deadline(*, mutation: bool) -> str:
    """Devolve o prazo padrão do Hypothesis em um processo com o ambiente dado."""
    env = os.environ.copy()
    env.pop("HYPOTHESIS_PROFILE", None)
    env.pop("KAIROS_MUTATION", None)
    if mutation:
        env["KAIROS_MUTATION"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import conftest; from hypothesis import settings; print(settings.default.deadline)",
        ],
        cwd=TESTS_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_developer_run_keeps_hypothesis_deadline() -> None:
    """Sem a variável de mutação, o prazo padrão do Hypothesis permanece ativo."""
    assert _default_deadline(mutation=False) != "None"


def test_mutation_run_disables_hypothesis_deadline() -> None:
    """No gate de mutação, o perfil dedicado remove apenas o prazo do Hypothesis."""
    assert _default_deadline(mutation=True) == "None"
