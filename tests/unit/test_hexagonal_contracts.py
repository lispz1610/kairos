"""Contratos arquiteturais hexagonalis verificados com ``import-linter``.

Os testes usam uma árvore Python mínima gravada em ``tmp_path`` para provar
tanto o caso válido quanto a detecção de importações proibidas entre o núcleo
e os adaptadores e de dependências web no núcleo.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

CONFIG = """\
[tool.importlinter]
root_package = "src"
include_external_packages = true

[[tool.importlinter.contracts]]
name = "ARQ-1: camadas hexagonais"
type = "layers"
containers = ["src"]
layers = ["adapters", "core"]

[[tool.importlinter.contracts]]
name = "ARQ-2: núcleo sem dependências de I/O web"
type = "forbidden"
source_modules = ["src.core"]
forbidden_modules = ["fastapi"]
allow_indirect_imports = false
"""


def _fixture(tmp_path: Path, core_source: str) -> Path:
    """Criar uma árvore com núcleo, adaptador e configuração de contratos."""
    root = tmp_path / "projeto"
    (root / "src/core").mkdir(parents=True)
    (root / "src/adapters").mkdir(parents=True)
    (root / "src/__init__.py").write_text("", encoding="utf-8")
    (root / "src/core/__init__.py").write_text("", encoding="utf-8")
    (root / "src/adapters/__init__.py").write_text("", encoding="utf-8")
    (root / "src/core/domain.py").write_text(core_source, encoding="utf-8")
    (root / "src/adapters/web.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(CONFIG, encoding="utf-8")
    return root


def _lint(root: Path) -> subprocess.CompletedProcess[str]:
    """Executar o import-linter sobre a configuração da árvore isolada."""
    executable = shutil.which("lint-imports")
    if executable is None:
        name = "lint-imports.exe" if os.name == "nt" else "lint-imports"
        local = Path(sys.executable).with_name(name)
        executable = str(local) if local.is_file() else None
    assert executable is not None, "import-linter precisa estar instalado (extra dev)"
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [executable, "--no-cache", "--no-logo", str(root / "pyproject.toml")],
        cwd=root,
        env=env,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )


def test_contratos_sao_kept_quando_nucleo_nao_importa_adapters(tmp_path: Path) -> None:
    """Uma árvore hexagonal mínima satisfaz os dois contratos declarados."""
    root = _fixture(tmp_path, "from datetime import datetime\n\nNOW = datetime(2026, 1, 1)\n")

    result = _lint(root)
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "ARQ-1" in output
    assert "ARQ-2" in output
    assert "0 broken" in output


def test_contrato_arq1_detecta_importacao_de_adapter_no_nucleo(tmp_path: Path) -> None:
    """O núcleo não pode importar módulos da camada de adaptadores."""
    root = _fixture(tmp_path, "from src.adapters import web\n\nVALUE = web.VALUE\n")

    result = _lint(root)
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert "ARQ-1" in output
    assert "src.core.domain" in output
    assert "src.adapters" in output


def test_contrato_arq2_detecta_dependencia_web_no_nucleo(tmp_path: Path) -> None:
    """O núcleo não pode importar bibliotecas HTTP/web."""
    root = _fixture(tmp_path, "import fastapi\n\nAPP = fastapi.FastAPI()\n")

    result = _lint(root)
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert "ARQ-2" in output
    assert "fastapi" in output
