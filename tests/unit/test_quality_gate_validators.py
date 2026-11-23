"""Testes de integração do gate rápido com os validadores da issue #86.

O script ``verify_quality.sh`` é copiado para uma árvore temporária junto com
os validadores e com documentos e suíte mínimos. Ferramentas externas são
substituídas por stubs, de modo que o teste exercite apenas a orquestração do
gate. Cada divergência proposital é aplicada à cópia, nunca ao repositório.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "verify_quality.sh"
VALIDATORS = (
    "validate_traceability.py",
    "generate_traceability_matrix.py",
    "validate_docs_as_code.py",
)
SPECIFICATION = (
    "\n".join(f"### RF{number:02d} — Requisito {number:02d}" for number in range(1, 9))
    + "\n"
)
PLAN = """# Plano de Testes ISO/IEC/IEEE 29119

## 7. Matriz de Rastreabilidade RF01–RF08 × testes

## 8. Lacunas conhecidas

1. **Backup/restauração JSON no navegador (RF08)**: sem testes de navegador nesta versão.
"""
HANDOFF = """# Handoff

## 4. Estado Atual

Documentação versionada.

## 5. Próximos Passos Imediatos para o Próximo Agente

1. Configuração do Projeto Python.
"""


def _tests_source() -> str:
    """Montar uma suíte mínima com um marcador para cada RF obrigatório."""
    cases = [
        f'@pytest.mark.requirement("RF{number:02d}")\n'
        f"def test_rf{number:02d}():\n"
        "    pass\n"
        for number in range(1, 9)
    ]
    return "import pytest\n\n\n" + "\n\n".join(cases)


def _write_stub(bin_dir: Path, name: str, body: str) -> None:
    """Gravar uma ferramenta simulada e executável no diretório de stubs."""
    path = bin_dir / name
    path.write_text(f"#!/usr/bin/env bash\nset -eu\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


def _fixture(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Copiar o gate para uma árvore isolada com documentos e suíte fiéis."""
    root = tmp_path / "project"
    (root / "scripts").mkdir(parents=True)
    (root / "docs/testing").mkdir(parents=True)
    (root / "tests/unit").mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    shutil.copy2(GATE, root / "verify_quality.sh")
    for name in VALIDATORS:
        shutil.copy2(REPO_ROOT / "scripts" / name, root / "scripts" / name)

    (root / "docs/especificacao-requisitos-funcionais.md").write_text(
        SPECIFICATION, encoding="utf-8"
    )
    plan = root / "docs/testing/test-plan-29119.md"
    plan.write_text(PLAN, encoding="utf-8")
    (root / "docs/HANDOFF.md").write_text(HANDOFF, encoding="utf-8")
    (root / "tests/unit/test_requirements.py").write_text(_tests_source(), encoding="utf-8")

    generated = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/generate_traceability_matrix.py"),
            "--plan",
            str(plan),
            "--spec",
            str(root / "docs/especificacao-requisitos-funcionais.md"),
            "--root",
            str(root),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stdout + generated.stderr

    _write_stub(bin_dir, "ruff", "exit 0\n")
    _write_stub(bin_dir, "mypy", "exit 0\n")
    _write_stub(bin_dir, "radon", 'echo "src/core/domain/events.py:1:0 -> funcao (3)"\n')
    _write_stub(bin_dir, "pytest", 'echo "TOTAL 100%"\n')

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    return root, env


def _run_gate(root: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Executar o gate na árvore isolada com as ferramentas simuladas."""
    return subprocess.run(
        ["bash", "./verify_quality.sh"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_gate_passa_com_documentos_e_marcadores_fieis(tmp_path: Path) -> None:
    """Documentos e suíte consistentes passam por todas as etapas do gate."""
    root, env = _fixture(tmp_path)

    result = _run_gate(root, env)
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Validação de rastreabilidade passou" in output
    assert "Verificação passou: matriz RF01–RF08 fiel" in output
    assert "Validação docs-as-code passou" in output
    assert "Quality gate PASSED" in output


def test_gate_falha_com_marcador_de_rf_inexistente(tmp_path: Path) -> None:
    """Um marcador apontando para RF inexistente derruba o gate."""
    root, env = _fixture(tmp_path)
    suite = root / "tests/unit/test_requirements.py"
    suite.write_text(
        suite.read_text(encoding="utf-8").replace('"RF03"', '"RF99"'),
        encoding="utf-8",
    )

    result = _run_gate(root, env)
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert "marcador requirement inválido" in output
    assert "RF99" in output
    assert "Quality gate PASSED" not in output


def test_gate_falha_com_matriz_desatualizada(tmp_path: Path) -> None:
    """Uma linha da matriz divergente da suíte derruba o gate via --check."""
    root, env = _fixture(tmp_path)
    plan = root / "docs/testing/test-plan-29119.md"
    plan.write_text(
        plan.read_text(encoding="utf-8").replace("test_rf01", "test_rf01_desatualizado"),
        encoding="utf-8",
    )

    result = _run_gate(root, env)
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert "VERIFICAÇÃO FALHOU" in output
    assert "RF01" in output
    assert "Quality gate PASSED" not in output


def test_gate_falha_com_contradicacao_docs_as_code(tmp_path: Path) -> None:
    """Uma pendência documentada sobre artefato existente derruba o gate."""
    root, env = _fixture(tmp_path)
    handoff = root / "docs/HANDOFF.md"
    handoff.write_text(
        handoff.read_text(encoding="utf-8")
        + "\n2. **Script de Automação de Qualidade**: `verify_quality.sh` executando `pytest`.\n",
        encoding="utf-8",
    )

    result = _run_gate(root, env)
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert "contradição docs-as-code" in output
    assert "verify_quality.sh" in output
    assert "Quality gate PASSED" not in output
