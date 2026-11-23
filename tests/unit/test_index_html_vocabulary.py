"""Testes de vocabulário canônico do template ``index.html``.

A GLOSSARY define os termos canônicos do domínio e lista os sinônimos evitados
(por exemplo, "Rota"/"Itinerário" para "Roteiro", "Hotel"/"base" para
"Hospedagem", "parada" para "Ponto de Interesse"). O teste original de #59
cobre o cartão do Dia de Viagem; os testes de #78 cobrem a estrutura e os textos
visíveis introduzidos pelos fluxos de Deslocamento em Cascata e Backup JSON,
sem tocar nos controles pré-existentes de Eventos de Contingência.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = REPO_ROOT / "src/adapters/web/templates/index.html"

# Termos evitados pelo GLOSSARY que seriam regressões visíveis nos novos fluxos.
AVOIDED_TERMS = (
    "Rota",
    "Rotas",
    "plano de viagem",
    "projeto de viagem",
    "itinerário",
    "Itinerário",
    "Hospedagem Base",
    "parada",
    "Orçamento",
    "previsão de custo",
    "estadia",
    "Voo",
    "viagem entre cidades",
    "Efeito dominó",
    "shift de datas",
)


def _html() -> str:
    """Lê o template servido pela aplicação web."""
    return INDEX_HTML.read_text(encoding="utf-8")


def _section(html: str, element_id: str) -> str:
    """Extrai o conteúdo de uma seção a partir do atributo ``id`` informado."""
    start = html.index(f'id="{element_id}"')
    end = html.index("</section>", start)
    return html[start:end]


def _script_function_body(html: str, name: str) -> str:
    """Extrai o corpo de uma função JavaScript declarada no template."""
    match = re.search(
        r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{(?P<body>[\s\S]*?)\n\}",
        html,
    )
    assert match is not None, f"Função JavaScript {name} não encontrada no template"
    return match.group("body")


def _visible_literals(body: str) -> str:
    """Extrai apenas as strings exibidas ao usuário de um corpo JavaScript."""
    return " ".join(re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', body))


def test_index_html_card_title_uses_canonical_vocabulary() -> None:
    """Verifica que o template index.html utiliza o vocabulário canônico sem o termo evitado."""
    html = _html()
    assert "Rota" not in html


def test_index_html_new_flow_sections_use_canonical_vocabulary() -> None:
    """Verifica rótulos canônicos nas seções de Viagem, modal e Backup JSON."""
    html = _html()
    sections = {
        "trip-planning": ("Viagem", "Etapa de Viagem", "Deslocamento em Cascata"),
        "trip-backup-controls": ("Backup JSON",),
    }
    for element_id, expected_terms in sections.items():
        content = _section(html, element_id)
        for term in expected_terms:
            assert term in content, f"{term} ausente na seção {element_id}"
        for term in AVOIDED_TERMS:
            assert term not in content, f"{term} inadequado na seção {element_id}"

    modal_start = html.index('id="modal-overlay"')
    modal = re.sub(r"<!--[\s\S]*?-->", "", html[modal_start : html.index("<footer>", modal_start)])
    for term in (
        "Datas anteriores",
        "Datas recalculadas",
        "Etapas de Viagem",
        "Conexões Interurbanas",
    ):
        assert term in modal, f"{term} ausente no Modal de Confirmação de Impacto"
    for term in AVOIDED_TERMS:
        assert term not in modal, f"{term} inadequado no Modal de Confirmação de Impacto"


def test_index_html_new_flow_scripts_use_canonical_vocabulary() -> None:
    """Verifica que os textos visíveis gerados pelos novos fluxos seguem o glossário."""
    html = _html()
    expected_terms = {
        "defaultTrip": ("Hospedagem",),
        "renderTripStages": ("Dia de Viagem", "Conexão Interurbana"),
        "showImpactModal": ("Etapa de Viagem", "Conexão Interurbana"),
        "previewRippleShift": ("Deslocamento em Cascata", "Viagem"),
        "confirmRippleShift": ("Deslocamento em Cascata", "Viagem"),
        "restoreTripBackup": ("Backup JSON", "Viagem"),
    }
    for function_name, terms in expected_terms.items():
        literals = _visible_literals(_script_function_body(html, function_name))
        for term in terms:
            assert term in literals, f"{term} ausente nos textos de {function_name}"
        for term in AVOIDED_TERMS:
            assert term not in literals, f"{term} inadequado nos textos de {function_name}"
