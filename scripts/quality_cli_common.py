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
import json
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
RAW_KEYS = ("loc", "lloc", "sloc", "comments", "single_comments", "multi", "blank")


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
        return {"value": None, "status": "unavailable"}
    average = round(sum(values) / len(values), 2)
    return {"value": {"min": min(values), "average": average}, "status": "measured"}


def parse_radon_raw(text: str) -> dict[str, object]:
    """Somar os volumes brutos por categoria relatados pelo radon raw."""
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
        return {"value": None, "status": "unavailable"}
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
        stats = json.loads(read_utf8(path))
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


MIN_COVERAGE = 85.0
MAX_COMPLEXITY = 9


def _section(report: Mapping[str, object], *keys: str) -> object | None:
    """Navegar com segurança por uma seção do relatório estruturado."""
    current: object = report
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _metric_value(metric: object | None) -> object | None:
    """Extrair o valor de uma medição, preservando ausências."""
    if isinstance(metric, Mapping) and "value" in metric:
        return metric["value"]
    return None


def _is_number(value: object) -> bool:
    """Identificar um número, excluindo booleanos."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def check_quality_thresholds(report: Mapping[str, object]) -> list[str]:
    """Listar violações dos limiares bloqueantes do gate de qualidade."""
    violations: list[str] = []
    coverage = _metric_value(
        _section(report, "standards", "iso_25010", "adequacao_funcional", "cobertura_percentual")
    )
    if _is_number(coverage) and coverage < MIN_COVERAGE:
        violations.append(f"cobertura {coverage}% abaixo do mínimo {MIN_COVERAGE:g}%")

    syntactic = _section(report, "standards", "iso_5055", "complexidade_sintatica", "value")
    maximum = syntactic.get("maxima") if isinstance(syntactic, Mapping) else None
    if _is_number(maximum) and maximum > MAX_COMPLEXITY:
        violations.append(
            f"complexidade sintática máxima {maximum} acima do limite {MAX_COMPLEXITY}"
        )

    zero_limits = (
        ("erros de tipagem", "confiabilidade", "erros_de_tipagem"),
        ("violações Ruff", "manutencionabilidade", "violacoes_ruff"),
        (
            "contratos arquiteturais rompidos",
            "manutencionabilidade",
            "violacoes_contrato_arquitetural",
        ),
        ("achados Bandit", "seguranca", "achados_bandit"),
    )
    for label, characteristic, metric in zero_limits:
        value = _metric_value(
            _section(report, "standards", "iso_25010", characteristic, metric)
        )
        if _is_number(value) and value > 0:
            violations.append(f"{label}: {value}")
    return violations


def _display(metric: object | None) -> str:
    """Formatar uma medição para o resumo de console."""
    if not isinstance(metric, Mapping):
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


def format_quality_summary(report: Mapping[str, object]) -> str:
    """Resumo determinístico do relatório consolidado para o console do gate."""
    raw_25010 = _section(report, "standards", "iso_25010")
    raw_5055 = _section(report, "standards", "iso_5055")
    iso_25010 = raw_25010 if isinstance(raw_25010, Mapping) else {}
    iso_5055 = raw_5055 if isinstance(raw_5055, Mapping) else {}
    coverage = _metric_value(
        _section(iso_25010, "adequacao_funcional", "cobertura_percentual")
    )
    syntactic = _section(iso_5055, "complexidade_sintatica")
    syntactic_value = syntactic.get("value") if isinstance(syntactic, Mapping) else None
    maximum = syntactic_value.get("maxima") if isinstance(syntactic_value, Mapping) else None
    inventory = _metric_value(_section(iso_5055, "inventario_estrutural"))
    docstrings = _metric_value(_section(iso_5055, "cobertura_de_docstrings"))
    mutation = _section(iso_25010, "confiabilidade", "mutacao")
    mutation_text = _display(mutation)
    coverage_text = _display(
        {"value": coverage, "status": "measured" if coverage is not None else "unavailable"}
    )
    complexity_text = maximum if maximum is not None else "não disponível"
    typing_text = _display(_section(iso_25010, "confiabilidade", "erros_de_tipagem"))
    ruff_text = _display(_section(iso_25010, "manutencionabilidade", "violacoes_ruff"))
    architecture_text = _display(
        _section(iso_25010, "manutencionabilidade", "violacoes_contrato_arquitetural")
    )
    bandit_text = _display(_section(iso_25010, "seguranca", "achados_bandit"))

    lines = [
        "==> Consolidated quality summary",
        f"  Coverage:                  {coverage_text} (minimum {MIN_COVERAGE:g}%)",
        f"  Max syntactic complexity:  {complexity_text} (limit < {MAX_COMPLEXITY + 1})",
        f"  Typing errors:             {typing_text}",
        f"  Ruff violations:           {ruff_text}",
        f"  Architecture violations:   {architecture_text}",
        f"  Bandit findings:           {bandit_text}",
        f"  Structural inventory:      {_display(inventory)}",
        f"  Docstring coverage:        {_display(docstrings)}",
        f"  Mutation (src/core):       {mutation_text}",
        "  Relatório ISO:             reports/quality-metrics.json / .md",
    ]
    return "\n".join(lines)
