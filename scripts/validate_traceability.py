#!/usr/bin/env python3
"""Validador offline de rastreabilidade entre requisitos funcionais e testes.

Os identificadores canônicos são lidos dos cabeçalhos ``### RFxx`` da
especificação de requisitos funcionais. Os marcadores ``requirement`` são
coletados por análise sintática (AST) dos arquivos de teste, sem importar a
suíte, sem coleta do pytest e sem acesso a rede ou credenciais.

A cobertura obrigatória é restrita a RF01–RF08. Identificadores adicionais
presentes na especificação (por exemplo, RF09–RF13) são aceitos como marcadores
válidos, mas não exigem caso de teste.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SPECIFICATION_ID_RE = re.compile(r"^###\s+(RF\d{2})\b", re.MULTILINE)
REQUIRED_IDS = frozenset(f"RF{number:02d}" for number in range(1, 9))

EPILOG = """Critério para lacunas parciais de navegador:
  Declarações documentais sobre interação em navegador real (por exemplo,
  backup/restauração JSON ou modal de confirmação) NÃO são lidas como um RF sem
  teste. A cobertura é atestada apenas pela presença de pelo menos um marcador
  @pytest.mark.requirement na suíte. Assim, um RF com marcador passa mesmo que
  o Plano de Testes descreva uma lacuna parcial de interface; um RF sem
  marcador falha, ainda que exista uma lacuna documentada. Marcadores RF09 a
  RF13 são válidos quando declarados na especificação, mas não obrigatórios.
"""


@dataclass(frozen=True)
class Marker:
    """Marcador ``requirement`` localizado na suíte de testes."""

    path: Path
    line: int
    identifier: str


def extract_canonical_ids(specification: Path) -> frozenset[str]:
    """Extrair os RFxx canônicos dos cabeçalhos de nível 3 da especificação."""
    return frozenset(SPECIFICATION_ID_RE.findall(specification.read_text(encoding="utf-8")))


def _dotted_name(node: ast.AST) -> str:
    """Reconstruir o nome pontuado de uma expressão de chamada."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _is_requirement_call(name: str) -> bool:
    """Reconhecer ``requirement(...)``, ``mark.requirement(...)`` e aliases."""
    if name == "requirement":
        return True
    parts = name.split(".")
    return len(parts) >= 2 and parts[-2:] == ["mark", "requirement"]


def _identifier_arguments(call: ast.Call) -> list[str]:
    """Ler os argumentos literais de um marcador ``requirement``."""
    return [
        argument.value
        for argument in call.args
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
    ]


def extract_markers(tests_dir: Path) -> list[Marker]:
    """Coletar marcadores por análise sintática dos arquivos de teste."""
    markers: list[Marker] = []
    if not tests_dir.is_dir():
        return markers
    for path in sorted(tests_dir.rglob("*.py")):
        if not (path.name.startswith("test_") or path.name.endswith("_test.py")):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_requirement_call(_dotted_name(node.func)):
                continue
            for identifier in _identifier_arguments(node):
                markers.append(Marker(path=path, line=node.lineno, identifier=identifier))
    return markers


def main(argv: list[str] | None = None) -> int:
    """Executar a validação de rastreabilidade a partir da linha de comando."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--spec",
        "--specification",
        dest="spec",
        type=Path,
        required=True,
        help="especificação de requisitos funcionais com cabeçalhos ### RFxx",
    )
    parser.add_argument(
        "--root",
        "--code-root",
        dest="root",
        type=Path,
        default=Path.cwd(),
        help="raiz da árvore de código (padrão: diretório atual)",
    )
    parser.add_argument(
        "--tests",
        "--tests-root",
        dest="tests",
        type=Path,
        default=None,
        help="diretório da suíte de testes (padrão: <raiz>/tests)",
    )
    args = parser.parse_args(argv)

    if not args.spec.is_file():
        print(f"Erro: especificação não encontrada: {args.spec}", file=sys.stderr)
        return 2
    if not args.root.is_dir():
        print(f"Erro: raiz de código não encontrada: {args.root}", file=sys.stderr)
        return 2
    tests_dir = args.tests if args.tests is not None else args.root / "tests"
    if args.tests is not None and not tests_dir.is_dir():
        print(f"Erro: diretório de testes não encontrado: {tests_dir}", file=sys.stderr)
        return 2

    try:
        canonical_ids = extract_canonical_ids(args.spec)
    except (OSError, UnicodeError) as error:
        print(f"Erro ao ler especificação: {error}", file=sys.stderr)
        return 2
    if not canonical_ids:
        print("Erro: a especificação não declara cabeçalhos ### RFxx.", file=sys.stderr)
        return 2
    try:
        markers = extract_markers(tests_dir)
    except (OSError, UnicodeError, SyntaxError) as error:
        print(f"Erro ao analisar suíte de testes: {error}", file=sys.stderr)
        return 2

    covered_ids = {marker.identifier for marker in markers}
    missing = sorted((REQUIRED_IDS & canonical_ids) - covered_ids)
    invalid = [marker for marker in markers if marker.identifier not in canonical_ids]

    for marker in invalid:
        print(
            f"{marker.path}:{marker.line}: marcador requirement inválido: "
            f"{marker.identifier} não existe na especificação"
        )
    for identifier in missing:
        print(f"{identifier}: requisito obrigatório sem caso de teste com marcador requirement")

    if invalid:
        print(
            f"VALIDAÇÃO FALHOU: {len(invalid)} marcador(es) apontam para RF inexistente.",
            file=sys.stderr,
        )
    if missing:
        print(
            f"VALIDAÇÃO FALHOU: {len(missing)} requisito(s) obrigatório(s) sem teste.",
            file=sys.stderr,
        )
    if invalid or missing:
        return 1

    print(
        "Validação de rastreabilidade passou: RF01 a RF08 possuem ao menos um teste "
        "e nenhum marcador aponta para RF inexistente."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
