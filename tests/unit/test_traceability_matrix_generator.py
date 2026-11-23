"""Testes de CLI do gerador/verificador da matriz RF × teste da issue #83.

Cada cenário usa ``tmp_path`` para fornecer Plano de Testes, especificação e
suíte isolados. As asserções observam códigos de saída, diagnósticos e o texto
do documento — nunca detalhes internos do gerador — e confirmam que seções não
relacionadas à matriz não são reescritas.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "scripts" / "generate_traceability_matrix.py"

CONTEXT = "## 1. Escopo\n\nTexto de contexto que não deve mudar.\n"
EXTENSION_ROW = (
    "| **Extensão dinâmica** | Evento de Contingência / Replanejamento | — | — | — "
    "| — (sem código); nenhuma cobertura automatizada nesta versão "
    "— lacuna declarada em §8. |"
)
EXTENSION_NOTE = (
    "**Extensão dinâmica (contingências)**: extensão prevista na especificação, "
    "sem RF próprio nem casos de teste nesta versão "
    "— registrada na linha de extensão dinâmica e em §8."
)
GAPS = (
    "## 8. Lacunas conhecidas\n\n"
    "1. **Modal de Confirmação (RF06)**: ainda sem implementação nem teste nesta versão.\n"
)
TABLE_HEADER = (
    "| RF | Requisito | Testes unitários | Testes de integração | "
    "Testes de propriedade | Código de produção relacionado |"
)


def _write(path: Path, text: str) -> None:
    """Gravar um arquivo de texto criando os diretórios intermediários."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _specification() -> str:
    """Montar uma especificação mínima com os RF01 a RF08 canônicos."""
    headings = "\n".join(
        f"### RF{number:02d} — Requisito {number:02d}" for number in range(1, 9)
    )
    return f"# Especificação de Requisitos Funcionais\n\n{headings}\n"


def _old_row(number: int, production: str = "Código antigo") -> str:
    """Montar uma linha RF desatualizada com célula de código preservável."""
    return f"| **RF{number:02d}** | Título antigo | — | — | — | {production} |"


def _plan() -> str:
    """Montar um Plano de Testes mínimo com matriz, extensão dinâmica e lacunas."""
    rows = "\n".join(
        _old_row(number, "**confirmação visual via modal não implementada (ver §8)**")
        if number == 6
        else _old_row(number)
        for number in range(1, 9)
    )
    return (
        "# Plano de Testes ISO/IEC/IEEE 29119\n\n"
        f"{CONTEXT}\n"
        "---\n\n"
        "## 7. Matriz de Rastreabilidade RF01–RF08 × testes\n\n"
        "Matriz derivada dos marcadores da suíte.\n\n"
        f"{TABLE_HEADER}\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"{rows}\n"
        f"{EXTENSION_ROW}\n\n"
        f"{EXTENSION_NOTE}\n\n"
        "---\n\n"
        f"{GAPS}"
    )


def _marked_test(identifiers: tuple[str, ...], name: str) -> str:
    """Montar um arquivo de teste com um marcador requirement."""
    arguments = ", ".join(f'"{identifier}"' for identifier in identifiers)
    return (
        "import pytest\n\n\n"
        f"@pytest.mark.requirement({arguments})\n"
        f"def {name}():\n"
        "    pass\n"
    )


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Criar especificação, Plano de Testes e suíte mínima isolados."""
    plan = tmp_path / "test-plan.md"
    specification = tmp_path / "especificacao.md"
    root = tmp_path / "code"
    _write(plan, _plan())
    _write(specification, _specification())
    _write(
        root / "tests/unit/test_trip.py",
        _marked_test(("RF01",), "test_trip_decomposition")
        + "\n\n"
        + _marked_test(("RF06",), "test_ripple_shift"),
    )
    _write(
        root / "tests/integration/test_api.py",
        _marked_test(("RF02",), "test_transition_endpoint")
        + "\n\n"
        + _marked_test(("RF01", "RF06"), "test_combined_endpoint"),
    )
    _write(
        root / "tests/property/test_properties.py",
        _marked_test(("RF06",), "test_ripple_invariant"),
    )
    return plan, specification, root


def _run(
    plan: Path, specification: Path, root: Path, *, check: bool = False
) -> subprocess.CompletedProcess[str]:
    """Executar a CLI com documentos e raiz explícitos, opcionalmente em modo check."""
    command = [
        sys.executable,
        str(GENERATOR),
        "--plan",
        str(plan),
        "--spec",
        str(specification),
        "--root",
        str(root),
    ]
    if check:
        command.append("--check")
    return subprocess.run(command, capture_output=True, text=True, cwd=root, check=False)


def _row(document: str, identifier: str) -> str:
    """Localizar a linha de um RF no documento gerado."""
    return next(line for line in document.splitlines() if line.startswith(f"| **{identifier}** |"))


def test_generation_updates_matrix_and_preserves_unrelated_sections(tmp_path: Path) -> None:
    """A geração atualiza só as linhas RF e mantém extensão, lacunas e contexto."""
    plan, specification, root = _fixture(tmp_path)

    result = _run(plan, specification, root)

    assert result.returncode == 0, result.stdout + result.stderr
    generated = plan.read_text(encoding="utf-8")
    rf01 = _row(generated, "RF01")
    assert "`tests/unit/test_trip.py` — `test_trip_decomposition`" in rf01
    assert "`tests/integration/test_api.py` — `test_combined_endpoint`" in rf01
    assert "`tests/unit/test_trip.py` — `test_trip_decomposition`" not in _row(generated, "RF02")
    assert "`test_ripple_invariant`" in _row(generated, "RF06")
    assert "| **RF01** | Requisito 01 |" in generated
    assert (
        "**confirmação visual via modal não implementada (ver §8)**" in _row(generated, "RF06")
    )
    assert EXTENSION_ROW in generated
    assert EXTENSION_NOTE in generated
    assert CONTEXT in generated
    assert GAPS in generated

    second = _run(plan, specification, root)
    assert second.returncode == 0, second.stdout + second.stderr
    assert plan.read_text(encoding="utf-8") == generated


def test_check_passes_for_generated_plan_without_writing(tmp_path: Path) -> None:
    """Um plano já gerado passa no check e não é alterado pelo modo verificação."""
    plan, specification, root = _fixture(tmp_path)
    assert _run(plan, specification, root).returncode == 0
    before = plan.read_bytes()

    result = _run(plan, specification, root, check=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Verificação passou" in result.stdout
    assert plan.read_bytes() == before


def test_check_detects_divergence_with_clear_diagnosis(tmp_path: Path) -> None:
    """Um novo marcador na suíte gera falha 1 com RF e teste divergentes."""
    plan, specification, root = _fixture(tmp_path)
    assert _run(plan, specification, root).returncode == 0
    before = plan.read_bytes()
    _write(
        root / "tests/unit/test_dining.py",
        _marked_test(("RF03",), "test_new_dining_case"),
    )

    result = _run(plan, specification, root, check=True)
    output = result.stdout + result.stderr

    assert result.returncode == 1, output
    assert "RF03" in output
    assert "test_new_dining_case" in output
    assert "esperado" in output
    assert "divergente" in output
    assert plan.read_bytes() == before


def test_check_ignores_changes_outside_matrix(tmp_path: Path) -> None:
    """Alterações em seções não relacionadas não invalidam a verificação."""
    plan, specification, root = _fixture(tmp_path)
    assert _run(plan, specification, root).returncode == 0
    plan.write_text(
        plan.read_text(encoding="utf-8") + "\n2. **Lacuna adicional**: registrada depois.\n",
        encoding="utf-8",
    )

    result = _run(plan, specification, root, check=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Verificação passou" in result.stdout
