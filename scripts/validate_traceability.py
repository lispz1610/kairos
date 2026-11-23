#!/usr/bin/env python3
"""Validador offline de rastreabilidade entre requisitos funcionais e testes.

Os identificadores canônicos, os títulos RFxx e os marcadores ``requirement``
são coletados pelo módulo compartilhado ``quality_cli_common``, por análise
sintática (AST) dos arquivos de teste, sem importar a suíte, sem coleta do
pytest e sem acesso a rede ou credenciais.

A cobertura obrigatória é restrita a RF01–RF08. Identificadores adicionais
presentes na especificação (por exemplo, RF09–RF13) são aceitos como marcadores
válidos, mas não exigem caso de teste.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from scripts import quality_cli_common as qc
except ImportError:  # pragma: no cover - execução direta do script
    import quality_cli_common as qc

EPILOG = """Critério para lacunas parciais de navegador:
  Declarações documentais sobre interação em navegador real (por exemplo,
  backup/restauração JSON ou modal de confirmação) NÃO são lidas como um RF sem
  teste. A cobertura é atestada apenas pela presença de pelo menos um marcador
  @pytest.mark.requirement na suíte. Assim, um RF com marcador passa mesmo que
  o Plano de Testes descreva uma lacuna parcial de interface; um RF sem
  marcador falha, ainda que exista uma lacuna documentada. Marcadores RF09 a
  RF13 são válidos quando declarados na especificação, mas não obrigatórios.
"""

__all__ = ("EPILOG", "main", "qc")


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

    tree = qc.resolve_code_tree(args.root, args.tests)

    if not args.spec.is_file():
        print(f"Erro: especificação não encontrada: {args.spec}", file=sys.stderr)
        return 2
    if not tree.root.is_dir():
        print(f"Erro: raiz de código não encontrada: {tree.root}", file=sys.stderr)
        return 2
    if args.tests is not None and not tree.tests.is_dir():
        print(f"Erro: diretório de testes não encontrado: {tree.tests}", file=sys.stderr)
        return 2

    try:
        canonical_ids = qc.extract_canonical_ids(args.spec)
    except (OSError, UnicodeError) as error:
        print(f"Erro ao ler especificação: {error}", file=sys.stderr)
        return 2
    if not canonical_ids:
        print("Erro: a especificação não declara cabeçalhos ### RFxx.", file=sys.stderr)
        return 2
    try:
        markers: list[qc.Marker] = qc.extract_markers(tree.tests)
    except (OSError, UnicodeError, SyntaxError) as error:
        print(f"Erro ao analisar suíte de testes: {error}", file=sys.stderr)
        return 2

    covered_ids = {marker.identifier for marker in markers}
    missing = sorted((qc.REQUIRED_IDS & canonical_ids) - covered_ids)
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
