#!/usr/bin/env python3
"""Gerar ou verificar a matriz RF01–RF08 × testes do Plano de Testes 29119.

A matriz é derivada exclusivamente dos marcadores ``requirement`` coletados pela
mesma análise sintática usada por ``validate_traceability.py`` — sem importar a
suíte, sem pytest e sem rede. Somente as linhas RF01–RF08 da seção da matriz são
recalculadas: cabeçalho, linha da extensão dinâmica, parágrafos de lacunas e
todas as demais seções do Plano de Testes permanecem intactos.

Modo padrão: reescreve a matriz em ``--plan`` quando ela diverge da suíte.
Modo ``--check``: não grava nada; retorna 0 se o documento já estiver fiel à
suíte e 1 com diagnóstico por RF quando houver divergência.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_traceability import (  # noqa: E402
    REQUIRED_IDS,
    Marker,
    extract_canonical_ids,
    extract_markers,
    extract_requirement_titles,
)

SECTION_HEADING_RE = re.compile(r"^##\s+\d+\.\s+Matriz de Rastreabilidade\b", re.MULTILINE)
NEXT_SECTION_RE = re.compile(r"^##\s+", re.MULTILINE)
RF_ROW_RE = re.compile(r"^\|\s*\*\*(RF\d{2})\*\*\s*\|")

LAYERS = ("unit", "integration", "property")
TABLE_HEADER = (
    "| RF | Requisito | Testes unitários | Testes de integração | "
    "Testes de propriedade | Código de produção relacionado |"
)
TABLE_SEPARATOR = "| --- | --- | --- | --- | --- | --- |"


def _read_plan(plan: Path) -> str:
    """Ler o Plano de Testes preservando as quebras de linha originais."""
    with plan.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _write_plan(plan: Path, text: str) -> bool:
    """Gravar o plano apenas quando o conteúdo mudar; informar se houve escrita."""
    if _read_plan(plan) == text:
        return False
    with plan.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    return True


def _newline(lines: list[str]) -> str:
    """Detectar a quebra de linha predominante na seção da matriz."""
    return "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"


def _section_bounds(lines: list[str]) -> tuple[int, int] | None:
    """Localizar o intervalo de linhas da seção da matriz no plano."""
    start = next(
        (index for index, line in enumerate(lines) if SECTION_HEADING_RE.match(line)),
        None,
    )
    if start is None:
        return None
    end = next(
        (index for index in range(start + 1, len(lines)) if NEXT_SECTION_RE.match(lines[index])),
        len(lines),
    )
    return start, end


def _cells(line: str) -> list[str]:
    """Extrair as células de uma linha de tabela Markdown."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _existing_rows(lines: list[str]) -> dict[str, list[str]]:
    """Indexar as células das linhas RF já presentes na matriz."""
    rows: dict[str, list[str]] = {}
    for line in lines:
        match = RF_ROW_RE.match(line)
        if match:
            rows[match.group(1)] = _cells(line)
    return rows


def _row_for(lines: list[str], identifier: str) -> str:
    """Localizar a linha de um RF em uma seção, sem quebra de linha."""
    for line in lines:
        match = RF_ROW_RE.match(line)
        if match and match.group(1) == identifier:
            return line.rstrip("\r\n")
    return ""


def _relative_path(marker: Marker, tests_dir: Path) -> Path:
    """Representar o arquivo do marcador relativo à raiz da suíte."""
    try:
        return marker.path.relative_to(tests_dir)
    except ValueError:
        return Path(marker.path.name)


def _display_path(marker: Marker, root: Path, tests_dir: Path) -> Path:
    """Representar o arquivo do marcador no formato ``tests/...`` da matriz."""
    try:
        return marker.path.relative_to(root)
    except ValueError:
        return _relative_path(marker, tests_dir)


def _layer_for(relative: Path) -> str:
    """Enquadrar o marcador em uma das três colunas de teste da matriz."""
    if len(relative.parts) > 1 and relative.parts[0] in LAYERS:
        return relative.parts[0]
    return "unit"


def _group_markers(
    markers: list[Marker], root: Path, tests_dir: Path
) -> dict[str, dict[str, list[str]]]:
    """Agrupar identificadores de casos de teste por RF e por camada."""
    grouped: dict[str, dict[str, list[str]]] = {
        identifier: {layer: [] for layer in LAYERS} for identifier in sorted(REQUIRED_IDS)
    }
    for marker in markers:
        if marker.identifier not in grouped:
            continue
        display = _display_path(marker, root, tests_dir)
        test_id = f"{display.as_posix()}::{marker.test}" if marker.test else display.as_posix()
        layer = _layer_for(_relative_path(marker, tests_dir))
        bucket = grouped[marker.identifier][layer]
        if test_id not in bucket:
            bucket.append(test_id)
    for layers in grouped.values():
        for bucket in layers.values():
            bucket.sort()
    return grouped


def _format_cell(test_ids: list[str]) -> str:
    """Formatar uma célula da matriz agrupando casos por arquivo de teste."""
    if not test_ids:
        return "—"
    by_file: dict[str, list[str]] = {}
    for test_id in test_ids:
        path, separator, name = test_id.partition("::")
        names = by_file.setdefault(path, [])
        entry = name if separator and name else "arquivo"
        if entry not in names:
            names.append(entry)
    descriptions: list[str] = []
    for path in sorted(by_file):
        names = ", ".join(
            f"`{name}`" if name != "arquivo" else "(arquivo)" for name in by_file[path]
        )
        descriptions.append(f"`{path}` — {names}")
    return "; ".join(descriptions)


def _build_rows(
    markers: list[Marker],
    titles: dict[str, str],
    root: Path,
    tests_dir: Path,
    section_lines: list[str],
) -> dict[str, str]:
    """Reconstruir as linhas RF01–RF08 a partir dos marcadores da suíte."""
    grouped = _group_markers(markers, root, tests_dir)
    existing = _existing_rows(section_lines)
    rows: dict[str, str] = {}
    for identifier in sorted(REQUIRED_IDS):
        cells = existing.get(identifier, [])
        title = titles.get(identifier) or (cells[1] if len(cells) > 1 else "—")
        production = cells[5] if len(cells) > 5 else "—"
        values = [
            f"**{identifier}**",
            title,
            *(_format_cell(grouped[identifier][layer]) for layer in LAYERS),
            production,
        ]
        rows[identifier] = "| " + " | ".join(values) + " |"
    return rows


def _insert_table(lines: list[str], rows: dict[str, str], newline: str) -> list[str]:
    """Criar a tabela da matriz quando a seção ainda não a contém."""
    block = [TABLE_HEADER + newline, TABLE_SEPARATOR + newline]
    block.extend(rows[identifier] + newline for identifier in sorted(rows))
    block.append(newline)
    if not lines:
        return block
    return [lines[0], *block, *lines[1:]]


def _render_section(section_lines: list[str], rows: dict[str, str], newline: str) -> list[str]:
    """Substituir apenas as linhas RF da seção, preservando todo o restante."""
    rendered: list[str] = []
    table_seen = False
    for line in section_lines:
        if not line.lstrip().startswith("|"):
            rendered.append(line)
            continue
        table_seen = True
        match = RF_ROW_RE.match(line)
        if match and match.group(1) in rows:
            rendered.append(rows[match.group(1)] + newline)
        else:
            rendered.append(line)
    return rendered if table_seen else _insert_table(rendered, rows, newline)


def build_expected(
    plan_text: str,
    markers: list[Marker],
    titles: dict[str, str],
    root: Path,
    tests_dir: Path,
) -> str | None:
    """Montar o texto esperado do Plano de Testes sem modificá-lo."""
    lines = plan_text.splitlines(keepends=True)
    bounds = _section_bounds(lines)
    if bounds is None:
        return None
    start, end = bounds
    section_lines = lines[start:end]
    rows = _build_rows(markers, titles, root, tests_dir, section_lines)
    rendered = _render_section(section_lines, rows, _newline(section_lines))
    return "".join([*lines[:start], *rendered, *lines[end:]])


def _diagnose(plan_text: str, expected: str) -> list[str]:
    """Descrever, por RF, por que a matriz do plano divergiu da suíte."""
    lines = plan_text.splitlines(keepends=True)
    expected_lines = expected.splitlines(keepends=True)
    bounds = _section_bounds(lines)
    if bounds is None:
        return ["a seção 'Matriz de Rastreabilidade' não foi encontrada no Plano de Testes."]
    start, end = bounds
    diagnostics: list[str] = []
    for identifier in sorted(REQUIRED_IDS):
        actual = _row_for(lines[start:end], identifier)
        wanted = _row_for(expected_lines[start:end], identifier)
        if actual != wanted:
            diagnostics.append(
                f"{identifier}: linha da matriz divergente dos marcadores da suíte.\n"
                f"  atual:    {actual or '<ausente>'}\n"
                f"  esperado: {wanted or '<ausente>'}"
            )
    if not diagnostics:
        diagnostics.append(
            "a seção da matriz difere do texto esperado fora das linhas RF01–RF08."
        )
    return diagnostics


def main(argv: list[str] | None = None) -> int:
    """Executar a geração ou verificação da matriz a partir da linha de comando."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan",
        "--test-plan",
        dest="plan",
        type=Path,
        required=True,
        help="Plano de Testes 29119 cuja seção §7 será gerada/verificada",
    )
    parser.add_argument(
        "--spec",
        "--specification",
        dest="spec",
        type=Path,
        required=True,
        help="especificação com cabeçalhos ### RFxx para os títulos canônicos",
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
    parser.add_argument(
        "--check",
        action="store_true",
        help="apenas verificar: 0 se fiel à suíte, 1 se divergente (sem gravar)",
    )
    args = parser.parse_args(argv)

    for document in (args.plan, args.spec):
        if not document.is_file():
            print(f"Erro: documento não encontrado: {document}", file=sys.stderr)
            return 2
    if not args.root.is_dir():
        print(f"Erro: raiz de código não encontrada: {args.root}", file=sys.stderr)
        return 2
    tests_dir = args.tests if args.tests is not None else args.root / "tests"
    if not tests_dir.is_dir():
        print(f"Erro: diretório de testes não encontrado: {tests_dir}", file=sys.stderr)
        return 2

    try:
        canonical_ids = extract_canonical_ids(args.spec)
        titles = extract_requirement_titles(args.spec)
        markers = extract_markers(tests_dir)
        plan_text = _read_plan(args.plan)
    except (OSError, UnicodeError, SyntaxError) as error:
        print(f"Erro ao ler entradas: {error}", file=sys.stderr)
        return 2
    if not canonical_ids:
        print("Erro: a especificação não declara cabeçalhos ### RFxx.", file=sys.stderr)
        return 2

    invalid = sorted(
        {marker.identifier for marker in markers if marker.identifier not in canonical_ids}
    )
    if invalid:
        print(
            "Erro: marcadores requirement apontam para RF inexistente: " + ", ".join(invalid),
            file=sys.stderr,
        )
        return 2

    expected = build_expected(plan_text, markers, titles, args.root, tests_dir)
    if expected is None:
        print(
            "Erro: seção 'Matriz de Rastreabilidade' não encontrada no Plano de Testes.",
            file=sys.stderr,
        )
        return 2

    if args.check:
        if plan_text == expected:
            print("Verificação passou: matriz RF01–RF08 fiel aos marcadores da suíte.")
            return 0
        for diagnostic in _diagnose(plan_text, expected):
            print(f"VERIFICAÇÃO FALHOU: {diagnostic}", file=sys.stderr)
        return 1

    if _write_plan(args.plan, expected):
        print(f"Matriz RF01–RF08 gerada a partir dos marcadores em {args.plan}.")
    else:
        print("Matriz RF01–RF08 já estava atualizada; nenhuma alteração gravada.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
