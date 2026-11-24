#!/usr/bin/env python3
"""Coletor consolidado de métricas ISO/IEC 25010 e ISO/IEC 5055 do Kairos.

O coletor não reinventa medições: ele lê os arquivos de saída produzidos pelo
gate ``verify_quality.sh`` (ruff, mypy, radon, pytest, import-linter, bandit,
pip-audit, vulture e, no modo ``--full``, mutmut), converte o que é observável
em um relatório JSON estruturado e o traduz para Markdown legível.

Nenhum valor é inventado quando uma ferramenta não foi executada: o campo
correspondente recebe ``status: "unavailable"``. No modo rápido o mutation
score é explicitamente registado como ``"not run"``. O relatório não define
limiar mínimo para mutação; a meta numérica fica para revisão posterior da
linha de base, conforme a issue #65.
"""

from __future__ import annotations

import argparse
import json
import re
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

RUFF_ISSUE_RE = re.compile(r"\.py:\d+:\d+:", re.MULTILINE)
RUFF_TOTAL_RE = re.compile(r"Found\s+(\d+)\s+error", re.IGNORECASE)
MYPY_ERROR_RE = re.compile(r"\berror:\b")
MYPY_TOTAL_RE = re.compile(r"Found\s+(\d+)\s+error", re.IGNORECASE)
CC_SCORE_RE = re.compile(r"\((\d+)\)")
MI_SCORE_RE = re.compile(r"\(\s*(\d+(?:\.\d+)?)\s*\)\s*$", re.MULTILINE)
RAW_ITEM_RE = re.compile(
    r"^\s*(LOC|LLOC|SLOC|Comments|Single comments|Multi|Blank):\s*(\d+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
COVERAGE_RE = re.compile(r"TOTAL\s+[^\n]*?(\d+(?:\.\d+)?)%\s*$", re.MULTILINE)
BANDIT_ISSUE_RE = re.compile(r"^>>\s*Issue:", re.MULTILINE)
IMPORT_LINTER_BROKEN_RE = re.compile(r"is broken|Broken contract", re.IGNORECASE)
VULTURE_RE = re.compile(r"\bunused\b", re.IGNORECASE)
VULNERABILITY_ID_RE = re.compile(r"CVE-\d{4}-\d+|GHSA-[a-z0-9-]+", re.IGNORECASE)

RAW_KEYS: tuple[str, ...] = (
    "loc",
    "lloc",
    "sloc",
    "comments",
    "single_comments",
    "multi",
    "blank",
)
COMPLEXITY_LIMIT = 9


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


def _count_matching_lines(pattern: re.Pattern[str], text: str) -> int:
    """Contar linhas que casam com um padrão, sem duplicar ocorrências."""
    return sum(1 for line in text.splitlines() if pattern.search(line))


def parse_ruff(text: str, available: bool = True) -> int | None:
    """Extrair o número de violações do ruff, se a saída foi produzida."""
    if not available:
        return None
    if not text.strip():
        return 0
    total = RUFF_TOTAL_RE.search(text)
    return int(total.group(1)) if total else _count_matching_lines(RUFF_ISSUE_RE, text)


def parse_mypy(text: str, available: bool = True) -> int | None:
    """Extrair o número de erros de tipagem do mypy."""
    if not available:
        return None
    if not text.strip() or "Success:" in text:
        return 0
    total = MYPY_TOTAL_RE.search(text)
    return int(total.group(1)) if total else _count_matching_lines(MYPY_ERROR_RE, text)


def parse_radon_cc(text: str) -> int | None:
    """Maior complexidade ciclomática numérica relatada pelo radon cc."""
    scores = [int(score) for score in CC_SCORE_RE.findall(text)]
    return max(scores) if scores else None


def parse_radon_mi(text: str) -> dict[str, object]:
    """Menor e médio índice de manutenibilidade relatados pelo radon mi."""
    values = [float(score) for score in MI_SCORE_RE.findall(text)]
    if not values:
        return _measurement(None)
    average = round(sum(values) / len(values), 2)
    return {"value": {"min": min(values), "average": average}, "status": "measured"}


def parse_radon_raw(text: str) -> dict[str, object]:
    """Somar os volumes brutos por categoria relatados pelo radon raw."""
    # O radon repete todos os valores no bloco `** Total **`; somá-lo também
    # duplicaria cada métrica. Considera-se apenas a seção por arquivo.
    per_file = text.split("** Total **", 1)[0]
    totals: dict[str, int] = {}
    for label, raw_value in RAW_ITEM_RE.findall(per_file):
        key = label.casefold().replace(" ", "_")
        totals[key] = totals.get(key, 0) + int(raw_value)
    value = {key: totals.get(key) for key in RAW_KEYS}
    return {"value": value, "status": "measured" if totals else "unavailable"}


def parse_coverage(text: str) -> float | None:
    """Última porcentagem TOTAL reportada pela suíte pytest-cov."""
    matches = COVERAGE_RE.findall(text)
    return float(matches[-1]) if matches else None


def parse_import_linter(text: str, available: bool = True) -> int | None:
    """Contar contratos arquiteturais rompidos pelo import-linter."""
    if not available:
        return None
    if not text.strip():
        return 0
    return _count_matching_lines(IMPORT_LINTER_BROKEN_RE, text)


def parse_bandit(text: str, available: bool = True) -> int | None:
    """Contar achados de segurança do bandit."""
    if not available:
        return None
    if not text.strip():
        return 0
    return _count_matching_lines(BANDIT_ISSUE_RE, text)


def parse_pip_audit(text: str, available: bool = True) -> dict[str, object]:
    """Resumir a auditoria de dependências sem inventar contagens ausentes."""
    if not available or not text.strip():
        return _measurement(None)
    if "No known vulnerabilities found" in text:
        return {"value": 0, "status": "measured", "policy": "warning"}
    identifiers = sorted(set(VULNERABILITY_ID_RE.findall(text)))
    if not identifiers:
        return {"value": None, "status": "review", "policy": "warning"}
    return {
        "value": len(identifiers),
        "status": "measured",
        "policy": "warning",
        "identifiers": identifiers,
    }


def parse_vulture(text: str, available: bool = True) -> int | None:
    """Contar itens de código potencialmente morto apontados pelo vulture."""
    if not available:
        return None
    if not text.strip():
        return 0
    return _count_matching_lines(VULTURE_RE, text)


def parse_mutmut(path: Path, full_mode: bool) -> dict[str, object]:
    """Calcular o mutation score somente quando o modo completo foi executado."""
    if not full_mode:
        return {"status": "not run", "score_percent": None}
    if not path.is_file():
        return {"status": "unavailable", "score_percent": None}
    try:
        stats = json.loads(qc.read_utf8(path))
    except (OSError, ValueError):
        return {"status": "unavailable", "score_percent": None}
    if not isinstance(stats, dict):
        return {"status": "unavailable", "score_percent": None}

    def number(key: str) -> int:
        """Ler um contador inteiro do JSON do mutmut com valor ausente igual a zero."""
        try:
            return int(stats.get(key, 0))
        except (TypeError, ValueError):
            return 0

    killed = number("killed")
    survived = number("survived")
    timeout = number("timeout")
    tested = number("total") - number("skipped")
    score = None if tested <= 0 else round((killed + timeout) / tested * 100, 1)
    return {
        "status": "measured" if score is not None else "unavailable",
        "score_percent": score,
        "killed": killed,
        "survived": survived,
        "timeout": timeout,
        "tested": tested,
    }


def collect(reports_dir: Path, full_mode: bool, generated_at: str) -> dict[str, object]:
    """Agregar todas as saídas em um único documento estruturado."""
    texts = {report.key: _read_report(reports_dir, report.filename) for report in REPORT_FILES}
    available = {
        report.key: (reports_dir / report.filename).is_file() for report in REPORT_FILES
    }

    coverage = parse_coverage(texts["pytest"]) if available["pytest"] else None
    complexity = parse_radon_cc(texts["radon_cc"]) if available["radon_cc"] else None
    mutation = parse_mutmut(reports_dir / "mutmut.json", full_mode)
    pip_audit = parse_pip_audit(texts["pip_audit"], available["pip_audit"])

    iso_25010: dict[str, dict[str, object]] = {
        "adequacao_funcional": {
            "cobertura_percentual": _measurement(coverage),
        },
        "confiabilidade": {
            "erros_de_tipagem": _measurement(parse_mypy(texts["mypy"], available["mypy"])),
            "mutacao": mutation,
        },
        "seguranca": {
            "achados_bandit": _measurement(parse_bandit(texts["bandit"], available["bandit"])),
            "vulnerabilidades_de_dependencias": pip_audit,
        },
        "manutencionabilidade": {
            "violacoes_contrato_arquitetural": _measurement(
                parse_import_linter(texts["import_linter"], available["import_linter"])
            ),
            "violacoes_ruff": _measurement(parse_ruff(texts["ruff"], available["ruff"])),
            "itens_de_codigo_morto": _measurement(
                parse_vulture(texts["vulture"], available["vulture"])
            ),
            "indice_de_manutencionabilidade": parse_radon_mi(texts["radon_mi"]),
            "volume_bruto": parse_radon_raw(texts["radon_raw"]),
        },
    }

    iso_5055: dict[str, object] = {
        "cobertura_percentual": _measurement(coverage),
        "complexidade_ciclomatica": {
            "maxima": _measurement(complexity),
            "limite": COMPLEXITY_LIMIT,
        },
        "indice_de_manutencionabilidade": parse_radon_mi(texts["radon_mi"]),
        "volume_bruto": parse_radon_raw(texts["radon_raw"]),
        "pontuacao_de_mutacao": mutation,
        "violacoes_ruff": _measurement(parse_ruff(texts["ruff"], available["ruff"])),
        "violacoes_contrato_arquitetural": _measurement(
            parse_import_linter(texts["import_linter"], available["import_linter"])
        ),
        "achados_bandit": _measurement(parse_bandit(texts["bandit"], available["bandit"])),
        "itens_de_codigo_morto": _measurement(
            parse_vulture(texts["vulture"], available["vulture"])
        ),
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
    if status == "not run":
        return "não executado"
    if status == "unavailable":
        return "não disponível"
    if "value" in metric:
        value = metric["value"]
        return "não medido" if value is None else str(value)
    return json.dumps(metric, ensure_ascii=False, sort_keys=True)


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
    args = parser.parse_args(argv)

    tree = qc.resolve_code_tree(args.root)
    if not tree.root.is_dir():
        print(f"Erro: raiz de código não encontrada: {tree.root}", file=sys.stderr)
        return 2

    report = collect(
        args.reports_dir,
        args.full,
        datetime.now(timezone.utc).isoformat(),
    )
    serialized = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
    _write_output(args.json_output, serialized)
    _write_output(args.markdown_output, render_markdown(report))
    print(f"Relatório JSON: {args.json_output}")
    print(f"Relatório Markdown: {args.markdown_output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
