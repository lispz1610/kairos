#!/usr/bin/env python3
"""Validador docs-as-code de lacunas e artefatos do Kairos.

Confronta afirmações verificáveis no Plano de Testes ISO/IEC/IEEE 29119 e as
pendências do HANDOFF com módulos, endpoints, scripts e suítes de teste
efetivamente presentes na árvore de código informada.

Critério de isenção: uma lacuna parcial de navegador só é ignorada quando a
própria ausência citada é de automação/interface/navegador na mesma oração
(por exemplo, "sem testes de navegador" ou "sem automação de interface"). Uma
afirmação de ausência total de código/testes de um componente presente NÃO é
isenção, ainda que o item também mencione navegador. Leitura UTF-8, agrupamento
de blocos com sua seção ``##`` e resolução de caminhos vêm de
``quality_cli_common``. A ferramenta é estritamente offline e não acessa rede.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from scripts import quality_cli_common as qc
except ImportError:  # pragma: no cover - execução direta do script
    import quality_cli_common as qc


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
    rf"(?:{CODE_ABSENCE_RE.pattern})|(?:{TEST_ABSENCE_RE.pattern})",
    re.IGNORECASE,
)
PARTIAL_BROWSER_GAP_RE = re.compile(
    r"(?:sem|n[aã]o\s+(?:h[aá]|existe|possui|s[aã]o)|faltam?|aus[eê]ncia\s+de|fora\s+de)"
    r"(?:[^\n.;,]*?\s+)?"
    r"(?:testes?|casos\s+de\s+teste|cobertura|automa[cç][aã]o|verifica[cç][aã]o"
    r"|exercitad[oa]s?|controles?)"
    r"(?:[^\n.;,]*?\s+)?"
    r"(?:de\s+|em\s+|por\s+|na\s+|no\s+|da\s+)?"
    r"(?:navegador|browser|selenium|playwright|localstorage|interface"
    r"|intera[cç][aã]o\s+gr[aá]fica|timeline)"
    r"|(?:n[aã]o\s+automatizado|fora\s+da\s+automa[cç][aã]o)"
    r"(?:[^\n.;,]*?\s+)?"
    r"(?:navegador|browser|interface|intera[cç][aã]o|timeline)",
    re.IGNORECASE,
)
CLAUSE_SEPARATOR_RE = re.compile(r"[.;,]")
PENDING_TITLE_RE = re.compile(r"^\d+\.\s*Pr[oó]ximos\s+Passos", re.IGNORECASE)

EPILOG = """Critério da isenção de lacuna parcial de navegador:
  Somente uma ausência explicitamente limitada a automação/interface/navegador
  na mesma oração (por exemplo, "sem testes de navegador" ou "sem automação de
  interface") deixa de ser contradição. Dizer que um componente está "sem
  código e sem testes" continua sendo ausência total e falha, ainda que o item
  mencione navegador em outra oração.
"""

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
    """Informar se algum termo do componente aparece no bloco documental."""
    return any(re.search(term, text, re.IGNORECASE) for term in rule.terms)


def _has_total_absence(text: str) -> bool:
    """Detectar ausência total após remover lacunas escopeadas de navegador."""
    for clause in CLAUSE_SEPARATOR_RE.split(text):
        remaining = PARTIAL_BROWSER_GAP_RE.sub(" ", clause)
        if TOTAL_ABSENCE_RE.search(remaining):
            return True
    return False


def extract_claims(path: Path) -> list[Claim]:
    """Extrair afirmações de ausência total e pendências de um documento."""
    claims: dict[tuple[str, str], Claim] = {}
    source = str(path)
    for block in qc.document_blocks(path):
        partial_browser_gap = bool(PARTIAL_BROWSER_GAP_RE.search(block.text))
        total_absence = _has_total_absence(block.text)
        if partial_browser_gap and not total_absence:
            continue
        pending_section = bool(PENDING_TITLE_RE.match(block.section))
        for rule in RULES:
            if not _matches_rule(rule, block.text):
                continue
            if pending_section:
                kind = "pending"
            elif total_absence:
                kind = "total-absence"
            else:
                continue
            claims.setdefault(
                (rule.key, kind),
                Claim(
                    source=source,
                    line=block.line,
                    rule=rule,
                    kind=kind,
                    text=block.text,
                ),
            )
    return list(claims.values())


def _present_artifacts(
    root: qc.CodeTree, artifacts: tuple[Artifact, ...], category: str
) -> list[str]:
    """Listar, com descrição legível, os artefatos efetivamente presentes."""
    descriptions: list[str] = []
    for artifact in artifacts:
        path = root.artifact(artifact.path)
        if not path.is_file():
            continue
        if artifact.marker:
            try:
                content = qc.read_utf8_lossy(path)
            except OSError:
                continue
            if artifact.marker not in content:
                continue
        detail = f" [contém {artifact.marker}]" if artifact.marker else ""
        descriptions.append(f"{category} {artifact.path}{detail}")
    return descriptions


def evaluate(claims: list[Claim], root: qc.CodeTree) -> list[Finding]:
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
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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
    tree = qc.resolve_code_tree(args.root)

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
