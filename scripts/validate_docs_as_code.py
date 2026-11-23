#!/usr/bin/env python3
"""Validador docs-as-code de lacunas e artefatos do Kairos.

Confronta afirmações verificáveis no Plano de Testes ISO/IEC/IEEE 29119 e as
pendências do HANDOFF com módulos, endpoints, scripts e suítes de teste
efetivamente presentes na árvore de código informada.

Uma lacuna parcial de interação em navegador (por exemplo, backup/restauração
JSON ou modal de confirmação) não é contradição: apenas ausências totais de
código/testes e tarefas marcadas como pendentes são verificadas. Leitura UTF-8,
descoberta de seções ``##`` e resolução de caminhos vêm de
``quality_cli_common``. A ferramenta é estritamente offline e não acessa rede.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from scripts.quality_cli_common import (
        CodeTree,
        iter_markdown_sections,
        read_utf8,
        resolve_code_tree,
    )
except ImportError:  # pragma: no cover - execução direta do script
    from quality_cli_common import (
        CodeTree,
        iter_markdown_sections,
        read_utf8,
        resolve_code_tree,
    )


@dataclass(frozen=True)
class Artifact:
    """Artefato verificável na árvore de código."""

    path: str
    marker: str = ""


@dataclass(frozen=True)
class ComponentRule:
    """Componente de domínio com termos documentais e artefatos esperados."""

    key: str
    label: str
    terms: tuple[str, ...]
    code: tuple[Artifact, ...]
    tests: tuple[Artifact, ...]


@dataclass(frozen=True)
class Claim:
    """Afirmação documental extraída de um documento de entrada."""

    source: str
    line: int
    rule: ComponentRule
    kind: str
    text: str


@dataclass(frozen=True)
class Finding:
    """Contradição detectada entre documento e árvore de código."""

    source: str
    line: int
    rule: ComponentRule
    kind: str
    present: tuple[str, ...]


CODE_ABSENCE_RE = re.compile(
    r"sem\s+c[oó]digo|sem\s+implementa[cç][aã]o|nem\s+implementa[cç][aã]o"
    r"|n[aã]o\s+implementad[oa]|n[aã]o\s+(?:h[aá]|existe)\s+c[oó]digo"
    r"|n[aã]o\s+possui\s+(?:.*\s+)?implementa[cç][aã]o",
    re.IGNORECASE,
)
TEST_ABSENCE_RE = re.compile(
    r"sem\s+testes?|sem\s+casos\s+de\s+teste|sem\s+cobertura"
    r"|nem\s+testes?|n[aã]o\s+(?:h[aá]|existe)\s+testes?",
    re.IGNORECASE,
)
TOTAL_ABSENCE_RE = re.compile(
    r"sem\s+c[oó]digo|sem\s+testes?|sem\s+casos\s+de\s+teste"
    r"|sem\s+implementa[cç][aã]o|nem\s+implementa[cç][aã]o"
    r"|n[aã]o\s+implementad[oa]|n[aã]o\s+(?:h[aá]|existe)\s+(?:c[oó]digo|testes?)"
    r"|n[aã]o\s+possui\s+(?:.*\s+)?implementa[cç][aã]o",
    re.IGNORECASE,
)
PARTIAL_BROWSER_RE = re.compile(
    r"navegador|browser|selenium|playwright|localstorage|modal"
    r"|intera[cç][aã]o\s+gr[aá]fica|testes?\s+de\s+interface",
    re.IGNORECASE,
)
PENDING_TITLE_RE = re.compile(r"^\d+\.\s*Pr[oó]ximos\s+Passos", re.IGNORECASE)

RULES: tuple[ComponentRule, ...] = (
    ComponentRule(
        key="contingency-events",
        label="Evento de Contingência",
        terms=(
            r"eventos?\s+de\s+conting[eê]ncia",
            r"conting[eê]ncia",
            r"delayevent",
            r"events\.py",
        ),
        code=(
            Artifact("src/core/domain/events.py", "DelayEvent"),
            Artifact("src/adapters/web/contingency.py", "apply_contingency_event"),
        ),
        tests=(
            Artifact("tests/unit/test_events.py"),
            Artifact("tests/unit/test_apply_contingency_event.py"),
        ),
    ),
    ComponentRule(
        key="replanning",
        label="Replanejamento",
        terms=(
            r"replanejamento",
            r"replan(?:ear|ning)?",
            r"rec[aá]lculo",
            r"/api/trip/replan",
            r"replanning\.py",
        ),
        code=(
            Artifact("src/core/services/replanning.py", "ReplanningService"),
            Artifact("src/adapters/web/app.py", "/api/trip/replan"),
        ),
        tests=(
            Artifact("tests/unit/test_replanning_service.py"),
            Artifact("tests/integration/test_trip_replan_endpoint.py"),
        ),
    ),
    ComponentRule(
        key="quality-gate-script",
        label="script de gate de qualidade",
        terms=(
            r"verify_quality\.sh",
            r"script\s+de\s+(?:automa[cç][aã]o\s+de\s+)?qualidade",
            r"quality\s+gate",
        ),
        code=(Artifact("verify_quality.sh", "pytest"),),
        tests=(),
    ),
)


def _matches_rule(rule: ComponentRule, text: str) -> bool:
    """Informar se algum termo do componente aparece na linha documental."""
    return any(re.search(term, text, re.IGNORECASE) for term in rule.terms)


def extract_claims(path: Path) -> list[Claim]:
    """Extrair afirmações de ausência total e pendências de um documento."""
    claims: dict[tuple[str, str], Claim] = {}
    source = str(path)
    lines = read_utf8(path).splitlines()
    pending_by_line = [False] * len(lines)
    for section in iter_markdown_sections(lines):
        is_pending = bool(PENDING_TITLE_RE.match(section.title))
        for index in range(section.start, section.end):
            pending_by_line[index] = is_pending
    for number, line in enumerate(lines, start=1):
        pending_section = pending_by_line[number - 1]
        if PARTIAL_BROWSER_RE.search(line):
            continue
        for rule in RULES:
            if not _matches_rule(rule, line):
                continue
            if pending_section:
                kind = "pending"
            elif TOTAL_ABSENCE_RE.search(line):
                kind = "total-absence"
            else:
                continue
            claims.setdefault(
                (rule.key, kind),
                Claim(source=source, line=number, rule=rule, kind=kind, text=line),
            )
    return list(claims.values())


def _present_artifacts(root: CodeTree, artifacts: tuple[Artifact, ...], category: str) -> list[str]:
    """Listar, com descrição legível, os artefatos efetivamente presentes."""
    descriptions: list[str] = []
    for artifact in artifacts:
        path = root.artifact(artifact.path)
        if not path.is_file():
            continue
        if artifact.marker:
            try:
                content = read_utf8(path, errors="replace")
            except OSError:
                continue
            if artifact.marker not in content:
                continue
        detail = f" [contém {artifact.marker}]" if artifact.marker else ""
        descriptions.append(f"{category} {artifact.path}{detail}")
    return descriptions


def evaluate(claims: list[Claim], root: CodeTree) -> list[Finding]:
    """Confrontar cada afirmação com os artefatos da árvore de código."""
    findings: list[Finding] = []
    for claim in claims:
        present_code = _present_artifacts(root, claim.rule.code, "código")
        present_tests = _present_artifacts(root, claim.rule.tests, "teste")
        if not present_code and not present_tests:
            continue
        if claim.kind == "pending":
            contradicted = True
        else:
            code_absent = bool(CODE_ABSENCE_RE.search(claim.text))
            tests_absent = bool(TEST_ABSENCE_RE.search(claim.text))
            if not code_absent and not tests_absent:
                code_absent = tests_absent = True
            contradicted = bool((code_absent and present_code) or (tests_absent and present_tests))
        if contradicted:
            findings.append(
                Finding(
                    source=claim.source,
                    line=claim.line,
                    rule=claim.rule,
                    kind=claim.kind,
                    present=tuple(present_code + present_tests),
                )
            )
    return findings


def format_finding(finding: Finding) -> str:
    """Formatar um diagnóstico legível em português."""
    if finding.kind == "pending":
        reason = "consta como pendente no handoff"
    else:
        reason = "foi declarado sem código e/ou testes"
    artifacts = "; ".join(finding.present)
    return (
        f"{finding.source}:{finding.line}: contradição docs-as-code: "
        f"{finding.rule.label} {reason}, mas a árvore contém: {artifacts}."
    )


def main(argv: list[str] | None = None) -> int:
    """Executar a validação docs-as-code a partir da linha de comando."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan",
        "--test-plan",
        dest="plan",
        type=Path,
        required=True,
        help="Plano de Testes 29119 a ser verificado",
    )
    parser.add_argument(
        "--handoff",
        type=Path,
        required=True,
        help="documento de handoff cujas pendências serão verificadas",
    )
    parser.add_argument(
        "--root",
        "--code-root",
        dest="root",
        type=Path,
        default=Path.cwd(),
        help="raiz da árvore de código (padrão: diretório atual)",
    )
    args = parser.parse_args(argv)
    tree = resolve_code_tree(args.root)

    for document in (args.plan, args.handoff):
        if not document.is_file():
            print(f"Erro: documento não encontrado: {document}", file=sys.stderr)
            return 2
    if not tree.root.is_dir():
        print(f"Erro: raiz de código não encontrada: {tree.root}", file=sys.stderr)
        return 2

    try:
        claims = extract_claims(args.plan) + extract_claims(args.handoff)
    except OSError as error:
        print(f"Erro ao ler documento: {error}", file=sys.stderr)
        return 2

    findings = evaluate(claims, tree)
    for finding in findings:
        print(format_finding(finding))
    if findings:
        print(
            f"VALIDAÇÃO FALHOU: {len(findings)} contradição(ões) docs-as-code.",
            file=sys.stderr,
        )
        return 1
    print("Validação docs-as-code passou: nenhuma contradição encontrada.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
