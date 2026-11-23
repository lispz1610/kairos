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

    for source in CLI_SOURCES:
        text = _source(source)
        assert "from scripts import quality_cli_common as qc" in text, (
            f"{source.name} não importa o módulo compartilhado como objeto"
        )
        assert "import quality_cli_common as qc" in text, (
            f"{source.name} não tem fallback direto equivalente"
        )
        assert "def extract_markers(" not in text, f"{source.name} duplica a coleta"


def test_validador_docs_as_code_reutiliza_leitura_agrupamento_e_caminhos() -> None:
    """O terceiro CLI consome os mesmos utilitários de documento e árvore."""
    text = _source(CLI_SOURCES[2])
    for helper in ("qc.read_utf8", "qc.document_blocks", "qc.resolve_code_tree"):
        assert helper in text, f"validate_docs_as_code não usa {helper}"


def test_agrupamento_de_blocos_com_secao_vem_do_modulo_compartilhado() -> None:
    """A extração de blocos e da seção ## correspondente tem implementação única."""
    shared = _source(SHARED_SOURCE)
    assert "class MarkdownBlock" in shared
    assert "def document_blocks(" in shared


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
        read_utf8_preserving_newlines,
        resolve_code_tree,
    )

    document = tmp_path / "documento.md"
    document.write_bytes(b"# Titulo\r\n## 1. Primeira\r\ntexto\r\n## 2. Segunda\r\n")

    assert read_utf8_preserving_newlines(document).count("\r\n") == 4
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


def test_document_blocks_agrupa_continuacao_e_para_em_delimitadores(tmp_path: Path) -> None:
    """A continuação preguiçosa não cruza item, cabeçalho, tabela, cerca ou break."""
    from scripts.quality_cli_common import document_blocks

    document = tmp_path / "blocos.md"
    document.write_text(
        """---
title: documento
---
## 8. Lacunas

1. Item sem
continue aqui
2. Outro item

| coluna | valor |
| --- | --- |

---

```
sem código e sem testes
```
""",
        encoding="utf-8",
    )

    blocks = document_blocks(document)
    first = next(block for block in blocks if block.text.startswith("1. Item sem"))

    assert first.line == 6
    assert first.section == "8. Lacunas"
    assert "continue aqui" in first.text
    assert "2. Outro item" not in first.text
    assert all("sem código e sem testes" not in block.text for block in blocks if block.line != 16)
