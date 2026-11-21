"""Teste de vocabulário de #59: o cartão do Dia de Viagem usa "Roteiro".

A GLOSSARY define "Roteiro" como o termo canônico para a sequência cronológica
de visitas a Pontos de Interesse (``_Avoid``: "Itinerário", "percurso",
"plano de viagem"; para "Deslocamento" também "rota"). Este teste afirma que o
cartão do Dia de Viagem do template ``index.html`` não contém o termo evitado
"Rota".
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_index_html_card_title_uses_canonical_vocabulary() -> None:
    html = (REPO_ROOT / "src/adapters/web/templates/index.html").read_text(encoding="utf-8")
    assert "Rota" not in html
