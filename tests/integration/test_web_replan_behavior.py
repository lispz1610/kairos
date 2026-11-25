"""Comportamento do fluxo JavaScript de Replanejamento via interface pública."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.requirement("RF03", "RF08", "RF12", "RF13")
def test_browser_replanning_flow() -> None:
    """Executa cenários de requisição e persistência no runtime JavaScript."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js indisponível para teste de comportamento JavaScript")
    script = Path(__file__).with_name("web_replan_behavior.cjs")
    result = subprocess.run(
        [node, "--test", str(script)],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
