#!/usr/bin/env python3
"""Utilitários compartilhados pelos CLIs de qualidade do Kairos.

Centraliza a leitura UTF-8 de documentos, a descoberta de seções ``##``, a
resolução da árvore de código e a única implementação da coleta de marcadores
``requirement`` e de títulos canônicos RFxx. Os CLIs importam este módulo como
qualquer outro, sem alterar a lista de busca de imports em tempo de execução.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

SPECIFICATION_ID_RE = re.compile(r"^###\s+(RF\d{2})\b", re.MULTILINE)
SPECIFICATION_TITLE_RE = re.compile(r"^###\s+(RF\d{2})\s+[—–-]\s*(.+?)\s*$", re.MULTILINE)
LEVEL2_HEADING_RE = re.compile(r"^##\s(.*?)\s*$")
REQUIRED_IDS = frozenset(f"RF{number:02d}" for number in range(1, 9))


@dataclass(frozen=True)
class Marker:
    """Marcador ``requirement`` localizado na suíte de testes."""

    path: Path
    line: int
    identifier: str
    test: str = ""


@dataclass(frozen=True)
class MarkdownSection:
    """Seção ``##`` de um documento e seu intervalo semiaberto de linhas."""

    title: str
    start: int
    end: int


@dataclass(frozen=True)
class CodeTree:
    """Raiz da árvore de código e diretório da suíte de testes."""

    root: Path
    tests: Path

    def artifact(self, relative: str | Path) -> Path:
        """Caminho de um artefato documentado relativo à raiz da árvore."""
        return self.root / Path(relative)


def read_utf8(
    path: Path, *, preserve_newlines: bool = False, errors: str = "strict"
) -> str:
    """Ler texto UTF-8, opcionalmente preservando as quebras de linha originais."""
    if not preserve_newlines and errors == "strict":
        return path.read_text(encoding="utf-8")
    newline = "" if preserve_newlines else None
    with path.open("r", encoding="utf-8", errors=errors, newline=newline) as handle:
        return handle.read()


def iter_markdown_sections(lines: Sequence[str]) -> Iterator[MarkdownSection]:
    """Descobrir seções ``##`` e os intervalos de linhas que as delimitam."""
    headings = [
        (index, match.group(1).strip())
        for index, line in enumerate(lines)
        if (match := LEVEL2_HEADING_RE.match(line))
    ]
    for position, (start, title) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        yield MarkdownSection(title=title, start=start, end=end)


def resolve_code_tree(root: Path, tests: Path | None = None) -> CodeTree:
    """Árvore de código com suíte explícita ou padrão ``<raiz>/tests``."""
    return CodeTree(root=root, tests=tests if tests is not None else root / "tests")


def extract_canonical_ids(specification: Path) -> frozenset[str]:
    """Extrair os RFxx canônicos dos cabeçalhos de nível 3 da especificação."""
    return frozenset(SPECIFICATION_ID_RE.findall(read_utf8(specification)))


def extract_requirement_titles(specification: Path) -> dict[str, str]:
    """Extrair o título canônico de cada RFxx dos cabeçalhos da especificação."""
    text = read_utf8(specification)
    return {identifier: title.strip() for identifier, title in SPECIFICATION_TITLE_RE.findall(text)}


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


def _decorating_functions(tree: ast.AST) -> dict[int, str]:
    """Associar o nó de um decorador ao nome do caso de teste que ele anota."""
    names: dict[int, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            names[id(decorator)] = node.name
    return names


def extract_markers(tests_dir: Path) -> list[Marker]:
    """Coletar marcadores por análise sintática dos arquivos de teste."""
    markers: list[Marker] = []
    if not tests_dir.is_dir():
        return markers
    for path in sorted(tests_dir.rglob("*.py")):
        if not (path.name.startswith("test_") or path.name.endswith("_test.py")):
            continue
        tree = ast.parse(read_utf8(path), filename=str(path))
        decorated = _decorating_functions(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_requirement_call(_dotted_name(node.func)):
                continue
            test_name = decorated.get(id(node), "")
            for identifier in _identifier_arguments(node):
                markers.append(
                    Marker(path=path, line=node.lineno, identifier=identifier, test=test_name)
                )
    return markers
