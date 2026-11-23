"""Auxiliares compartilhados para os contratos do HTML servido pela aplicação web."""

import json
import re
from typing import Any


def _script_function_body(html: str, name: str) -> str:
    """Extrai o corpo de uma função JavaScript declarada no HTML servido."""
    match = re.search(
        r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{(?P<body>[\s\S]*?)\n\}",
        html,
    )
    assert match is not None, f"Função JavaScript {name} não encontrada no HTML"
    return match.group("body")


def element_attributes(html: str, element_id: str) -> dict[str, str]:
    """Devolve os atributos declarados no elemento com o ``id`` informado."""
    match = re.search(r"<[^>]*\bid=\"" + re.escape(element_id) + r"\"[^>]*>", html)
    assert match is not None, f"Elemento com id {element_id} não encontrado no HTML"
    return {
        name: value
        for name, value in re.findall(r"([a-zA-Z][\w:-]*)=\"([^\"]*)\"", match.group())
    }


def message_catalog(html: str) -> dict[str, str]:
    """Lê o catálogo de mensagens visíveis declarado no HTML servido."""
    match = re.search(
        r"<script type=\"application/json\" id=\"ui-messages\">(.*?)</script>",
        html,
        re.DOTALL,
    )
    assert match is not None, "Catálogo de mensagens visíveis não encontrado no HTML"
    catalog: dict[str, str] = json.loads(match.group(1))
    return catalog


def visible_literals(body: str) -> str:
    """Extrai as strings exibidas ao usuário de um corpo JavaScript."""
    return " ".join(re.findall(r"\"([^\"\\]*(?:\\.[^\"\\]*)*)\"", body))


def json_block(html: str, element_id: str) -> Any:
    """Lê um bloco JSON declarado no HTML pelo seu ``id``."""
    match = re.search(
        r"<script type=\"application/json\" id=\"" + re.escape(element_id) + r"\">"
        r"(.*?)</script>",
        html,
        re.DOTALL,
    )
    assert match is not None, f"Bloco JSON {element_id} não encontrado no HTML"
    return json.loads(match.group(1))
