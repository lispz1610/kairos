#!/usr/bin/env python3
"""Utilitários compartilhados pelos CLIs de qualidade do Kairos.

Centraliza a leitura UTF-8 de documentos, o agrupamento de blocos Markdown com
sua seção ``##``, a resolução da árvore de código e a única implementação da
coleta de marcadores ``requirement`` e de títulos canônicos RFxx. Os CLIs
importam este módulo como objeto, sem alterar a lista de busca de imports em
tempo de execução.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

SPECIFICATION_ID_RE = re.compile(r"^###\s+(RF\d{2})\b", re.MULTILINE)
SPECIFICATION_TITLE_RE = re.compile(r"^###\s+(RF\d{2})\s+[—–-]\s*(.+?)\s*$", re.MULTILINE)
LEVEL2_HEADING_RE = re.compile(r"^##\s(.*?)\s*$")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
BLOCK_BOUNDARY_RE = re.compile(
    r"^(?:"
    r"\s*(?:[-*+]|\d+[.)])\s+"  # novo item de lista
    r"|\s{0,3}#{1,6}\s"  # cabeçalho
    r"|\s*(?:```|~~~)"  # cerca de código
    r"|\s*(?:---|\+\+\+|===|\*\*\*|___)\s*$"  # front matter / linha temática
    r"|\s*\|"  # linha de tabela
    r")"
)
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
class MarkdownBlock:
    """Item de lista ou parágrafo, com a seção ``##`` que o contém."""

    line: int
    text: str
    section: str


@dataclass(frozen=True)
class CodeTree:
    """Raiz da árvore de código e diretório da suíte de testes."""

    root: Path
    tests: Path

    def artifact(self, relative: str | Path) -> Path:
        """Caminho de um artefato documentado relativo à raiz da árvore."""
        return self.root / Path(relative)


def read_utf8(path: Path) -> str:
    """Ler texto UTF-8 estrito, com as quebras de linha convertidas pelo Python."""
    return path.read_text(encoding="utf-8")


def read_utf8_preserving_newlines(path: Path) -> str:
    r"""Ler texto UTF-8 preservando as quebras ``\r\n`` originais."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def read_utf8_lossy(path: Path) -> str:
    """Ler texto UTF-8 substituindo bytes inválidos, para inspeção de artefatos."""
    return path.read_text(encoding="utf-8", errors="replace")


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


def document_blocks(path: Path) -> tuple[MarkdownBlock, ...]:
    """Agrupar itens de lista e suas continuações preguiçosas com a seção ``##``.

    A continuação pode vir na linha não indentada seguinte; ela termina em novo
    item, cabeçalho, cerca, front matter, linha temática ou linha de tabela,
    evitando misturar escopos diferentes de um mesmo documento.
    """
    lines = read_utf8(path).splitlines()
    sections = tuple(iter_markdown_sections(lines))
    blocks: list[MarkdownBlock] = []
    section_index = 0
    section = ""
    index = 0
    while index < len(lines):
        while section_index < len(sections) and sections[section_index].start <= index:
            section = sections[section_index].title
            section_index += 1
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        end = index + 1
        if LIST_ITEM_RE.match(line):
            while end < len(lines) and not BLOCK_BOUNDARY_RE.match(lines[end]):
                end += 1
        blocks.append(
            MarkdownBlock(
                line=index + 1,
                text="\n".join(lines[index:end]).rstrip(),
                section=section,
            )
        )
        index = end
    return tuple(blocks)


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
    for path in iter_python_files(tests_dir):
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


def iter_python_files(directory: Path) -> Iterator[Path]:
    """Iterar arquivos Python de uma árvore em ordem determinística."""
    if not directory.is_dir():
        return
    for path in sorted(directory.rglob("*.py")):
        if "__pycache__" not in path.parts:
            yield path


_COMPLEXITY_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.IfExp,
)
COMPLEXITY_BUCKETS = ("1-3", "4-6", "7-9", "10+")


def _own_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """Percorrer um corpo sem entrar em funções, classes ou lambdas aninhadas."""
    for child in ast.iter_child_nodes(node):
        yield child
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield from _own_nodes(child)


def cyclomatic_complexity(node: ast.AST) -> int:
    """Complexidade ciclomática sintática de uma função ou método."""
    total = 1
    for child in _own_nodes(node):
        if isinstance(child, _COMPLEXITY_NODES):
            total += 1
        elif isinstance(child, ast.BoolOp):
            total += len(child.values) - 1
        elif isinstance(child, ast.comprehension):
            total += len(child.ifs)
        elif isinstance(child, ast.Match):
            total += len(child.cases)
    return total


@dataclass
class _LayerCounts:
    """Contadores brutos usados para derivar o inventário de uma camada."""

    modules: int = 0
    classes: int = 0
    functions: int = 0
    methods: int = 0
    documented_modules: int = 0
    documented_classes: int = 0
    documented_functions: int = 0
    documented_methods: int = 0
    scores: list[int] = field(default_factory=list)
    distribution: dict[str, int] = field(
        default_factory=lambda: {bucket: 0 for bucket in COMPLEXITY_BUCKETS}
    )

    def add(self, other: _LayerCounts) -> None:
        """Somar outra camada a estes contadores."""
        self.modules += other.modules
        self.classes += other.classes
        self.functions += other.functions
        self.methods += other.methods
        self.documented_modules += other.documented_modules
        self.documented_classes += other.documented_classes
        self.documented_functions += other.documented_functions
        self.documented_methods += other.documented_methods
        self.scores.extend(other.scores)
        for bucket in COMPLEXITY_BUCKETS:
            self.distribution[bucket] += other.distribution[bucket]

    def as_dict(self) -> dict[str, object]:
        """Converta os contadores em um inventário pronto para JSON."""
        entities = self.modules + self.classes + self.functions + self.methods
        documented = (
            self.documented_modules
            + self.documented_classes
            + self.documented_functions
            + self.documented_methods
        )
        coverage = None if entities == 0 else round(documented / entities * 100, 1)
        average = None if not self.scores else round(sum(self.scores) / len(self.scores), 1)
        return {
            "modules": self.modules,
            "classes": self.classes,
            "functions": self.functions,
            "methods": self.methods,
            "documented_modules": self.documented_modules,
            "documented_classes": self.documented_classes,
            "documented_functions": self.documented_functions,
            "documented_methods": self.documented_methods,
            "docstring_coverage_percent": coverage,
            "complexity_max": max(self.scores) if self.scores else None,
            "complexity_average": average,
            "complexity_distribution": dict(self.distribution),
        }


def _complexity_bucket(score: int) -> str:
    """Classificar uma complexidade em faixas estáveis de auditoria."""
    if score <= 3:
        return "1-3"
    if score <= 6:
        return "4-6"
    if score <= 9:
        return "7-9"
    return "10+"


def _record_score(counts: _LayerCounts, score: int) -> None:
    """Registrar a complexidade de uma função no inventário da camada."""
    counts.scores.append(score)
    counts.distribution[_complexity_bucket(score)] += 1


_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _is_documented(node: ast.AST) -> bool:
    """Verificar se um nó possui docstring efetiva."""
    return ast.get_docstring(node) is not None


def _record_function(node: ast.AST, counts: _LayerCounts, method: bool) -> None:
    """Contar uma função ou método e registrar sua complexidade."""
    if method:
        counts.methods += 1
        if _is_documented(node):
            counts.documented_methods += 1
    else:
        counts.functions += 1
        if _is_documented(node):
            counts.documented_functions += 1
    _record_score(counts, cyclomatic_complexity(node))


def _inspect_module(tree: ast.AST, counts: _LayerCounts) -> None:
    """Contar entidades, docstrings e complexidade de um módulo Python."""
    counts.modules += 1
    if _is_documented(tree):
        counts.documented_modules += 1

    methods = {
        id(child)
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        for child in node.body
        if isinstance(child, _FUNCTION_NODES)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            counts.classes += 1
            if _is_documented(node):
                counts.documented_classes += 1
            for child in node.body:
                if isinstance(child, _FUNCTION_NODES):
                    _record_function(child, counts, method=True)
        elif isinstance(node, _FUNCTION_NODES) and id(node) not in methods:
            _record_function(node, counts, method=False)


def _inventory_layer(directory: Path) -> _LayerCounts:
    """Montar os contadores de uma camada a partir de seus arquivos Python."""
    counts = _LayerCounts()
    for path in iter_python_files(directory):
        tree = ast.parse(read_utf8(path), filename=str(path))
        _inspect_module(tree, counts)
    return counts


def build_structural_inventory(
    root: Path,
    layers: Mapping[str, str | Path] | None = None,
) -> dict[str, dict[str, object]]:
    """Inventariar módulos, classes, funções, docstrings e complexidade por camada."""
    if layers is None:
        targets = {"core": root / "src/core", "adapters": root / "src/adapters"}
    else:
        targets = {}
        for name, value in layers.items():
            candidate = Path(value)
            targets[name] = candidate if candidate.is_absolute() else root / candidate

    result: dict[str, dict[str, object]] = {}
    total = _LayerCounts()
    for name, directory in targets.items():
        counts = _inventory_layer(directory)
        result[name] = counts.as_dict()
        total.add(counts)
    result["total"] = total.as_dict()
    return result


