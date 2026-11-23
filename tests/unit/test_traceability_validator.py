"""Testes de CLI do validador de rastreabilidade RF × teste da issue #80.

Cada cenário usa ``tmp_path`` para fornecer uma especificação e uma suíte
isoladas, verificando apenas códigos de saída e mensagens diagnósticas. O estado
de anotação do repositório real muda nas issues #81/#82, por isso não é usado
como expectativa nestes testes.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_traceability.py"


def _write(path: Path, text: str) -> None:
    """Gravar um arquivo de texto criando os diretórios intermediários."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _specification() -> str:
    """Montar uma especificação mínima com os RF01 a RF13 canônicos."""
    headings = "\n".join(
        f"### RF{number:02d} — Requisito {number:02d}" for number in range(1, 14)
    )
    return f"# Especificação de Requisitos Funcionais\n\n{headings}\n"


def _fixture(
    tmp_path: Path, test_markers: dict[str, tuple[str, ...]]
) -> tuple[Path, Path]:
    """Criar especificação e suíte temporárias com os marcadores informados."""
    specification = tmp_path / "especificacao.md"
    _write(specification, _specification())
    root = tmp_path / "code"
    for filename, identifiers in test_markers.items():
        arguments = ", ".join(f'"{identifier}"' for identifier in identifiers)
        source = (
            "import pytest\n\n\n"
            f"@pytest.mark.requirement({arguments})\n"
            f"def test_{filename[:-3]}():\n"
            "    pass\n"
        )
        _write(root / "tests" / filename, source)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    return specification, root


def _run(specification: Path, root: Path) -> subprocess.CompletedProcess[str]:
    """Executar a CLI do validador com especificação e raiz explícitas."""
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--spec",
            str(specification),
            "--root",
            str(root),
        ],
        capture_output=True,
        text=True,
        cwd=root,
        check=False,
    )


def test_suite_integra_com_marcadores_de_rf01_a_rf08(tmp_path: Path) -> None:
    """A presença de marcadores para RF01–RF08 e RF09 é suficiente para passar."""
    markers = {f"test_rf_{number:02d}.py": (f"RF{number:02d}",) for number in range(1, 9)}
    markers["test_contingencia.py"] = ("RF09",)
    specification, root = _fixture(tmp_path, markers)

    result = _run(specification, root)
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Validação de rastreabilidade passou" in output
    assert "sem caso de teste" not in output
    assert "marcador requirement inválido" not in output


def test_rf_obrigatorio_sem_teste_falha_com_diagnostico(tmp_path: Path) -> None:
    """Um RF01–RF08 sem marcador gera código 1 e diagnóstico com o identificador."""
    markers = {
        f"test_rf_{number:02d}.py": (f"RF{number:02d}",)
        for number in range(1, 9)
        if number != 3
    }
    specification, root = _fixture(tmp_path, markers)

    result = _run(specification, root)
    output = result.stdout + result.stderr

    assert result.returncode == 1, output
    assert "RF03" in output
    assert "sem caso de teste" in output


def test_marcador_com_rf_inexistente_falha_com_diagnostico(tmp_path: Path) -> None:
    """Um marcador apontando para RF fora da especificação gera código 1."""
    markers = {f"test_rf_{number:02d}.py": (f"RF{number:02d}",) for number in range(1, 9)}
    markers["test_rf_invalido.py"] = ("RF99",)
    specification, root = _fixture(tmp_path, markers)

    result = _run(specification, root)
    output = result.stdout + result.stderr

    assert result.returncode == 1, output
    assert "RF99" in output
    assert "inexistente" in output


def test_especificacao_ausente_retorna_codigo_de_uso(tmp_path: Path) -> None:
    """Especificação inexistente é erro de entrada, não falha de rastreabilidade."""
    _, root = _fixture(tmp_path, {})

    result = _run(tmp_path / "inexistente.md", root)

    assert result.returncode == 2
    assert "especificação não encontrada" in result.stderr


def test_ajuda_documenta_criterio_de_lacunas_parciais() -> None:
    """A ajuda da CLI explica como lacunas parciais de navegador são tratadas."""
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "lacunas parciais de navegador" in result.stdout
