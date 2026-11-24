#!/usr/bin/env python3
"""Coletor consolidado de métricas ISO/IEC 25010 e ISO/IEC 5055 do Kairos.

O coletor não reinventa medições: ele consome os parsers e o inventário AST de
``scripts/quality_cli_common.py`` sobre as saídas produzidas pelo gate
``verify_quality.sh`` (ruff, mypy, radon, pytest, import-linter, bandit,
pip-audit, vulture e, no modo ``--full``, mutmut), converte o que é observável
em um relatório JSON estruturado e o traduz para Markdown legível.

Nenhum valor é inventado quando uma ferramenta não foi executada: o campo
correspondente recebe ``status: "unavailable"``. No modo rápido o mutation
score é explicitamente registado como ``"not run"``. O relatório não define
limiar mínimo para mutação; a meta numérica fica para revisão posterior da
linha de base, conforme a issue #65.

A opção ``--check`` imprime o resumo consolidado e aplica os limiares
bloqueantes em ``quality_cli_common.check_quality_thresholds``, devolvendo 1 em
caso de violação. É essa interface que ``verify_quality.sh`` consome, sem
parsers próprios em shell.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts import quality_cli_common as qc
except ImportError:  # pragma: no cover - execução direta do script
    import quality_cli_common as qc


@dataclass(frozen=True)
class ReportFile:
    """Arquivo de saída de uma ferramenta dentro do diretório de relatórios."""

    key: str
    filename: str


REPORT_FILES: tuple[ReportFile, ...] = (
    ReportFile("ruff", "ruff.txt"),
    ReportFile("mypy", "mypy.txt"),
    ReportFile("radon_cc", "radon_cc.txt"),
    ReportFile("radon_mi", "radon_mi.txt"),
    ReportFile("radon_raw", "radon_raw.txt"),
    ReportFile("pytest", "pytest.txt"),
    ReportFile("import_linter", "import_linter.txt"),
    ReportFile("bandit", "bandit.txt"),
    ReportFile("pip_audit", "pip_audit.txt"),
    ReportFile("vulture", "vulture.txt"),
)

# Aliases públicos preservados para consumidores que importavam as funções do
# coletor antes da consolidação na issue #106. As implementações são únicas no
# módulo compartilhado.
COMPLEXITY_LIMIT = qc.MAX_COMPLEXITY
parse_ruff = qc.parse_ruff
parse_mypy = qc.parse_mypy
parse_radon_cc = qc.parse_radon_cc
parse_radon_mi = qc.parse_radon_mi
parse_radon_raw = qc.parse_radon_raw
parse_coverage = qc.parse_coverage
parse_import_linter = qc.parse_import_linter
parse_bandit = qc.parse_bandit
parse_pip_audit = qc.parse_pip_audit
parse_vulture = qc.parse_vulture
parse_mutmut = qc.parse_mutmut


def _read_report(reports_dir: Path, filename: str) -> str:
    """Ler uma saída de ferramenta; ausência devolve texto vazio."""
    path = reports_dir / filename
    if not path.is_file():
        return ""
    return qc.read_utf8_lossy(path)


def _measurement(value: object | None) -> dict[str, object]:
    """Representar um valor medido ou explicitamente indisponível."""
    status = "unavailable" if value is None else "measured"
    return {"value": value, "status": status}


def _syntactic_complexity(inventory: dict[str, dict[str, object]]) -> dict[str, object]:
    """Montar a métrica de complexidade sintática a partir do inventário AST."""
    total = inventory.get("total", {})
    maximum = total.get("complexity_max") if isinstance(total, dict) else None
    average = total.get("complexity_average") if isinstance(total, dict) else None
    by_layer = {
        name: data["complexity_max"]
        for name, data in inventory.items()
        if name != "total" and isinstance(data, dict) and "complexity_max" in data
    }
    return {
        "value": {
            "maxima": maximum,
            "media": average,
            "por_camada": by_layer,
        },
        "status": "measured" if maximum is not None else "unavailable",
        "limite": qc.MAX_COMPLEXITY,
    }


def collect(
    reports_dir: Path,
    full_mode: bool,
    generated_at: str,
    root: Path | None = None,
) -> dict[str, object]:
    """Agregar todas as saídas e o inventário AST em um único documento estruturado."""
    texts = {report.key: _read_report(reports_dir, report.filename) for report in REPORT_FILES}
    available = {
        report.key: (reports_dir / report.filename).is_file() for report in REPORT_FILES
    }

    coverage = qc.parse_coverage(texts["pytest"]) if available["pytest"] else None
    radon_complexity = qc.parse_radon_cc(texts["radon_cc"]) if available["radon_cc"] else None
    mutation = qc.parse_mutmut(reports_dir / "mutmut.json", full_mode)
    pip_audit = qc.parse_pip_audit(texts["pip_audit"], available["pip_audit"])

    inventory = qc.build_structural_inventory(root) if root is not None else {}
    inventory_measurement = _measurement(inventory) if inventory else _measurement(None)
    total_inventory = inventory.get("total", {})
    docstrings = (
        total_inventory.get("docstring_coverage_percent")
        if isinstance(total_inventory, dict)
        else None
    )
    syntactic = _syntactic_complexity(inventory)
    maintainability_index = qc.parse_radon_mi(texts["radon_mi"])
    raw_volume = qc.parse_radon_raw(texts["radon_raw"])
    ruff_violations = _measurement(qc.parse_ruff(texts["ruff"], available["ruff"]))
    architecture_violations = _measurement(
        qc.parse_import_linter(texts["import_linter"], available["import_linter"])
    )
    dead_code = _measurement(qc.parse_vulture(texts["vulture"], available["vulture"]))
    typing_errors = _measurement(qc.parse_mypy(texts["mypy"], available["mypy"]))
    bandit_findings = _measurement(qc.parse_bandit(texts["bandit"], available["bandit"]))

    iso_25010: dict[str, dict[str, object]] = {
        "adequacao_funcional": {
            "cobertura_percentual": _measurement(coverage),
        },
        "confiabilidade": {
            "erros_de_tipagem": typing_errors,
            "mutacao": mutation,
        },
        "seguranca": {
            "achados_bandit": bandit_findings,
            "vulnerabilidades_de_dependencias": pip_audit,
        },
        "manutencionabilidade": {
            "violacoes_contrato_arquitetural": architecture_violations,
            "violacoes_ruff": ruff_violations,
            "itens_de_codigo_morto": dead_code,
            "indice_de_manutencionabilidade": maintainability_index,
            "volume_bruto": raw_volume,
            "inventario_estrutural": inventory_measurement,
            "cobertura_de_docstrings": _measurement(docstrings),
        },
    }

    iso_5055: dict[str, object] = {
        "cobertura_percentual": _measurement(coverage),
        "complexidade_ciclomatica": {
            "maxima": _measurement(radon_complexity),
            "limite": COMPLEXITY_LIMIT,
        },
        "complexidade_sintatica": syntactic,
        "indice_de_manutencionabilidade": maintainability_index,
        "volume_bruto": raw_volume,
        "pontuacao_de_mutacao": mutation,
        "violacoes_ruff": ruff_violations,
        "violacoes_contrato_arquitetural": architecture_violations,
        "achados_bandit": bandit_findings,
        "itens_de_codigo_morto": dead_code,
        "inventario_estrutural": inventory_measurement,
        "cobertura_de_docstrings": _measurement(docstrings),
    }

    tools = {
        report.key: {
            "report": report.filename,
            "available": available[report.key],
        }
        for report in REPORT_FILES
    }
    tools["mutmut"] = {
        "report": "mutmut.json",
        "available": full_mode and (reports_dir / "mutmut.json").is_file(),
    }

    return {
        "generated_at": generated_at,
        "mode": "full" if full_mode else "fast",
        "reports_dir": str(reports_dir),
        "standards": {"iso_25010": iso_25010, "iso_5055": iso_5055},
        "tools": tools,
    }


def _format_metric(metric: object) -> str:
    """Formatar um valor para a tabela legível do Markdown."""
    if not isinstance(metric, dict):
        return "não medido" if metric is None else str(metric)
    status = metric.get("status")
    status_labels = {"not run": "não executado", "unavailable": "não disponível"}
    if status in status_labels:
        return status_labels[status]
    if "value" not in metric:
        return json.dumps(metric, ensure_ascii=False, sort_keys=True)
    value = metric["value"]
    if value is None:
        return "não medido"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def render_markdown(report: dict[str, object]) -> str:
    """Gerar Markdown agrupado por norma a partir do relatório estruturado."""
    standards = report["standards"]
    if not isinstance(standards, dict):
        return "# Relatório de Qualidade\n\ndados indisponíveis\n"
    iso_25010 = standards.get("iso_25010", {})
    iso_5055 = standards.get("iso_5055", {})

    lines = [
        "# Relatório Consolidado de Qualidade — Kairos",
        "",
        f"- Gerado em: {report['generated_at']}",
        f"- Modo: {report['mode']}",
        f"- Diretório de saídas: {report['reports_dir']}",
        "",
        "## ISO/IEC 25010 — características de qualidade",
        "",
    ]
    if isinstance(iso_25010, dict):
        for characteristic, metrics in iso_25010.items():
            lines.extend([f"### {characteristic}", ""])
            if isinstance(metrics, dict):
                for name, metric in metrics.items():
                    lines.append(f"- **{name}**: {_format_metric(metric)}")
            lines.append("")

    lines.extend(
        ["## ISO/IEC 5055 — qualidade estrutural", "", "| Métrica | Valor |", "| --- | --- |"]
    )
    if isinstance(iso_5055, dict):
        for name, metric in iso_5055.items():
            lines.append(f"| {name} | {_format_metric(metric)} |")
    lines.extend(
        [
            "",
            "O mutation score é evidência medida; não há meta mínima fixada nesta entrega.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_output(path: Path, content: str) -> None:
    """Gravar um relatório, criando os diretórios intermediários."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Executar a coleta a partir da linha de comando."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="raiz do repositório (padrão: diretório atual)",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("reports/tool-output"),
        help="diretório com as saídas das ferramentas",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("reports/quality-metrics.json"),
        help="caminho do relatório JSON",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("reports/quality-metrics.md"),
        help="caminho do relatório Markdown",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="inclui o mutation score produzido pelo modo --full do gate",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="imprime o resumo consolidado e falha se algum limiar for violado",
    )
    args = parser.parse_args(argv)

    tree = qc.resolve_code_tree(args.root)
    if not tree.root.is_dir():
        print(f"Erro: raiz de código não encontrada: {tree.root}", file=sys.stderr)
        return 2

    report = collect(
        args.reports_dir,
        args.full,
        datetime.now(timezone.utc).isoformat(),
        root=tree.root,
    )
    serialized = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
    _write_output(args.json_output, serialized)
    _write_output(args.markdown_output, render_markdown(report))
    print(f"Relatório JSON: {args.json_output}")
    print(f"Relatório Markdown: {args.markdown_output}")

    if args.check:
        print(qc.format_quality_summary(report))
        violations = qc.check_quality_thresholds(report)
        if violations:
            for violation in violations:
                print(f"  VIOLATION: {violation}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
