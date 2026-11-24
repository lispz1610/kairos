"""Contratos da API unificada de métricas de qualidade (issue #106).

Os testes exercitam diretamente as funções públicas de
``scripts.quality_cli_common`` com árvores e relatórios sintéticos em
``tmp_path``. Nenhum marcador ``requirement`` é acrescentado, preservando a
matriz RF × teste.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from scripts import quality_cli_common as qc


def _write(path: Path, content: str) -> None:
    """Gravar um arquivo de código/font, criando os diretórios intermediários."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_inventario_ast_separa_camadas_e_contabiliza_docstrings(tmp_path: Path) -> None:
    """O inventário distingue core/adapters, métodos, funções e docstrings."""
    _write(
        tmp_path / "src/core/mod.py",
        '"""Módulo central."""\n'
        "\n"
        "class Core:\n"
        '    """Serviço do núcleo."""\n'
        "\n"
        "    def run(self, value):\n"
        "        if value:\n"
        "            return 1\n"
        "        return 0\n"
        "\n"
        "\n"
        "def top():\n"
        "    return 2\n",
    )
    _write(tmp_path / "src/core/other.py", "def plain():\n    return 3\n")
    _write(
        tmp_path / "src/adapters/mod.py",
        "class Adapter:\n"
        "    def fetch(self, values):\n"
        "        for value in values:\n"
        "            if value:\n"
        "                return value\n"
        "        return None\n",
    )

    inventory = qc.build_structural_inventory(tmp_path)

    core = inventory["core"]
    adapters = inventory["adapters"]
    total = inventory["total"]
    assert core["modules"] == 2
    assert core["classes"] == 1
    assert core["methods"] == 1
    assert core["functions"] == 2
    assert core["documented_modules"] == 1
    assert core["documented_classes"] == 1
    assert core["docstring_coverage_percent"] == 33.3
    assert core["complexity_max"] == 2
    assert adapters["modules"] == 1
    assert adapters["methods"] == 1
    assert adapters["docstring_coverage_percent"] == 0.0
    assert adapters["complexity_max"] == 3
    assert total["modules"] == 3
    assert total["classes"] == 2
    assert total["methods"] == 2
    assert total["functions"] == 2
    assert total["docstring_coverage_percent"] == 22.2
    assert total["complexity_distribution"] == {"1-3": 4, "4-6": 0, "7-9": 0, "10+": 0}


def test_inventario_e_deterministico_e_ignora_pycache(tmp_path: Path) -> None:
    """A mesma árvore produz inventários idênticos, sem __pycache__."""
    _write(tmp_path / "src/core/mod.py", '"""Doc."""\n\ndef f():\n    return 1\n')
    _write(tmp_path / "src/core/__pycache__/ignored.py", "def noisy():\n    return 0\n")

    first = qc.build_structural_inventory(tmp_path)
    second = qc.build_structural_inventory(tmp_path)

    assert first == second
    assert first["core"]["modules"] == 1
    assert first["core"]["functions"] == 1


def test_complexidade_ignora_corpos_aninhados(tmp_path: Path) -> None:
    """A complexidade de uma função não incorpora funções aninhadas."""
    source = (
        "def outer(flag):\n"
        "    if flag:\n"
        "        return 1\n"
        "    def inner(value):\n"
        "        if value:\n"
        "            return 2\n"
        "        if value > 1:\n"
        "            return 3\n"
        "        return 4\n"
        "    return inner(flag)\n"
    )
    path = tmp_path / "aninhados.py"
    _write(path, source)
    tree = ast.parse(qc.read_utf8(path), filename=str(path))
    outer = next(node for node in tree.body if getattr(node, "name", "") == "outer")

    assert qc.cyclomatic_complexity(outer) == 2


def test_parsers_compartilhados_preservam_ausencias_e_score(tmp_path: Path) -> None:
    """Os parsers não inventam valores e unificam o cálculo do mutation score."""
    assert qc.parse_ruff("", available=False) is None
    assert qc.parse_ruff("") == 0
    assert qc.parse_mypy("Success: no issues found in 1 source file") == 0
    assert qc.parse_coverage("TOTAL 100 0 91.25%\n") == 91.25
    assert qc.parse_radon_raw("LOC: 4\n** Total **\nLOC: 4\n")["value"]["loc"] == 4
    assert qc.parse_mutmut(tmp_path / "ausente.json", full_mode=True)["status"] == "unavailable"
    assert qc.parse_mutmut(tmp_path / "ausente.json", full_mode=False)["status"] == "not run"

    stats = tmp_path / "mutmut.json"
    stats.write_text(
        json.dumps({"killed": 3, "survived": 1, "timeout": 1, "skipped": 2, "total": 8}),
        encoding="utf-8",
    )
    mutation = qc.parse_mutmut(stats, full_mode=True)
    assert mutation["status"] == "measured"
    assert mutation["score_percent"] == 66.7
    assert mutation["tested"] == 6


def _report(coverage: float, maximum: int, errors: int = 0) -> dict[str, object]:
    """Montar um relatório mínimo para verificação de limiares."""
    def measured(value: object) -> dict[str, object]:
        """Montar uma medição disponível para o relatório sintético."""
        return {"value": value, "status": "measured"}

    return {
        "standards": {
            "iso_25010": {
                "adequacao_funcional": {"cobertura_percentual": measured(coverage)},
                "confiabilidade": {
                    "erros_de_tipagem": measured(errors),
                    "mutacao": {"status": "not run", "score_percent": None},
                },
                "seguranca": {"achados_bandit": measured(0)},
                "manutencionabilidade": {
                    "violacoes_ruff": measured(0),
                    "violacoes_contrato_arquitetural": measured(0),
                },
            },
            "iso_5055": {
                "complexidade_sintatica": {
                    "value": {"maxima": maximum, "media": 2.0, "por_camada": {}},
                    "status": "measured",
                    "limite": qc.MAX_COMPLEXITY,
                }
            },
        }
    }


def test_limiares_unificados_aprovam_e_reprovam() -> None:
    """O mesmo contrato aprova valores válidos e lista cada violação."""
    assert qc.check_quality_thresholds(_report(85.0, 9)) == []

    violations = qc.check_quality_thresholds(_report(84.0, 10, errors=2))
    assert len(violations) == 3
    assert any("cobertura 84.0%" in item for item in violations)
    assert any("complexidade sintática máxima 10" in item for item in violations)
    assert any("erros de tipagem: 2" in item for item in violations)


def test_resumo_consolido_expõe_metricas_e_mutacao() -> None:
    """O resumo de console réplica o relatório sem recalcular valores."""
    summary = qc.format_quality_summary(_report(95.0, 8))

    assert "==> Consolidated quality summary" in summary
    assert "Coverage:                  95.0 (minimum 85%)" in summary
    assert "Max syntactic complexity:  8 (limit < 10)" in summary
    assert "Mutation (src/core):       não executado" in summary
