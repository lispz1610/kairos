"""Contratos de importação compartilhada dos CLIs de qualidade (issue #94).

Os testes observam apenas interfaces públicas: a execução dos CLIs como script e
como módulo, os arquivos-fonte entregues como artefatos e os utilitários
exportados para reutilização. Nenhum marcador ``requirement`` é acrescentado
a esta suíte, preservando a matriz RF × teste.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_NAMES = (
    "validate_traceability",
    "generate_traceability_matrix",
    "validate_docs_as_code",
)
CLI_SOURCES = tuple(REPO_ROOT / "scripts" / f"{name}.py" for name in CLI_NAMES)
SHARED_SOURCE = REPO_ROOT / "scripts" / "quality_cli_common.py"


def _source(path: Path) -> str:
    """Ler o código-fonte de um CLI como texto UTF-8."""
    return path.read_text(encoding="utf-8")


def test_clis_nao_alteram_path_de_imports_nem_suprimem_avisos_de_lint() -> None:
    """Nenhum CLI de qualidade manipula sys.path ou silencia regra de import."""
    for source in CLI_SOURCES:
        text = _source(source)
        assert "sys.path" not in text, f"{source.name} manipula sys.path"
        assert "# noqa" not in text, f"{source.name} suprime aviso de lint"


def test_coleta_de_marcadores_e_titulos_tem_uma_unica_implementacao() -> None:
    """Validador e gerador importam a mesma coleta de RF do módulo compartilhado."""
    shared = _source(SHARED_SOURCE)
    for definition in (
        "def extract_canonical_ids(",
        "def extract_requirement_titles(",
        "def extract_markers(",
    ):
        assert definition in shared

    for source in CLI_SOURCES[:2]:
        text = _source(source)
        assert "quality_cli_common import" in text, f"{source.name} não reutiliza o módulo"
        assert "def extract_markers(" not in text, f"{source.name} duplica a coleta"

    assert "def extract_markers(" not in _source(CLI_SOURCES[2])


def test_validador_docs_as_code_reutiliza_leitura_secoes_e_caminhos() -> None:
    """O terceiro CLI consome os mesmos utilitários de documento e árvore."""
    text = _source(CLI_SOURCES[2])
    for helper in ("read_utf8", "iter_markdown_sections", "resolve_code_tree"):
        assert helper in text, f"validate_docs_as_code não usa {helper}"


def test_clis_funcionam_como_script_e_como_modulo() -> None:
    """As duas formas documentadas de invocação carregam o módulo compartilhado."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    for name in CLI_NAMES:
        as_script = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / f"{name}.py"), "--help"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert as_script.returncode == 0, as_script.stdout + as_script.stderr

        as_module = subprocess.run(
            [sys.executable, "-m", f"scripts.{name}", "--help"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert as_module.returncode == 0, as_module.stdout + as_module.stderr


def test_utilitarios_compartilhados_preservam_leitura_secoes_e_caminhos(tmp_path: Path) -> None:
    """Os utilitários entregam leitura UTF-8, seções ## e raiz resolvida."""
    from scripts.quality_cli_common import (
        iter_markdown_sections,
        read_utf8,
        resolve_code_tree,
    )

    document = tmp_path / "documento.md"
    document.write_bytes(b"# Titulo\r\n## 1. Primeira\r\ntexto\r\n## 2. Segunda\r\n")

    assert read_utf8(document, preserve_newlines=True).count("\r\n") == 4
    sections = list(iter_markdown_sections(read_utf8(document).splitlines()))
    assert [(section.title, section.start, section.end) for section in sections] == [
        ("1. Primeira", 1, 3),
        ("2. Segunda", 3, 4),
    ]

    root = tmp_path / "codigo"
    tree = resolve_code_tree(root)
    assert tree.root == root
    assert tree.tests == root / "tests"
    assert tree.artifact("docs/plano.md") == root / "docs" / "plano.md"

    explicit = resolve_code_tree(root, tmp_path / "suited externa")
    assert explicit.tests == tmp_path / "suited externa"
