"""Contratos HTTP e de estrutura HTML da interface web (RF06/RF08)."""

import re

from fastapi.testclient import TestClient

from src.adapters.web.app import app
from tests.html_contract import element_attributes, message_catalog

client = TestClient(app)


def _html() -> str:
    """Obtém o HTML servido pela página inicial."""
    return client.get("/").text


def test_health_check() -> None:
    """Verifica que o endpoint de saúde responde com o status da aplicação."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "kairos"}


def test_index_page_renders_html() -> None:
    """Verifica que a página inicial renderiza o HTML da aplicação."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Kairos — Traçador Dinâmico de Rotas Turísticas" in response.text
    assert "kairos_trip_state_v1" in response.text
    assert "leaflet" in response.text.lower()


def test_index_page_keeps_day_contingency_controls() -> None:
    """Verifica que a seção do Dia de Viagem preserva seus controles e chave própria."""
    html = _html()
    for element_id in (
        "impact-banner",
        "stops",
        "apply-delay",
        "apply-closure",
        "apply-skip",
        "apply-adjust",
    ):
        assert f'id="{element_id}"' in html
    assert "kairos_trip_state_v1" in html


def test_index_page_exposes_trip_planning_section() -> None:
    """Expõe resumo, seletor e variação de dias com rótulos canônicos e chave dedicada."""
    html = _html()
    assert 'id="trip-planning"' in html
    assert "Planejamento da Viagem" in html
    assert 'id="trip-stages"' in html
    assert element_attributes(html, "trip-stages")["data-role"] == "trip-stage-summary"
    assert element_attributes(html, "trip-planning")["data-trip-storage-key"] == "kairos_trip_v1"
    assert element_attributes(html, "trip-planning")["data-trip-fallback"] == "deterministic-seed"
    assert element_attributes(html, "stage-selector")["aria-label"] == "Etapa de Viagem"
    assert "Variação de dias" in html
    assert "Variação de dias (delta_days)" not in html
    assert element_attributes(html, "delta-days")["type"] == "number"
    assert element_attributes(html, "preview-ripple-shift") == {
        "type": "button",
        "id": "preview-ripple-shift",
        "data-action": "preview-ripple-shift",
        "data-endpoint": "/api/trip/ripple-shift/preview",
    }


def test_index_page_exposes_impact_confirmation_modal() -> None:
    """O modal declara campos observáveis para datas, partidas e linha de impacto."""
    html = _html()
    for element_id in (
        "modal-overlay",
        "modal-title",
        "modal-body",
        "modal-impact-list",
        "modal-cancel-btn",
        "modal-close-btn",
        "modal-confirm-btn",
        "impact-row-template",
    ):
        assert f'id="{element_id}"' in html
    assert "Modal de Confirmação de Impacto" in html
    assert "Datas anteriores" in html
    assert "Datas recalculadas" in html
    assert "Etapas de Viagem" in html
    assert "Conexões Interurbanas" in html
    assert element_attributes(html, "modal-impact-list")["data-role"] == "impact-list"
    assert element_attributes(html, "impact-row-template")["data-role"] == "impact-row"
    for field in (
        "target-stage-start",
        "target-stage-end",
        "stage",
        "connection-date",
        "connection-departure",
    ):
        assert f'data-impact-field="{field}"' in html, f"Campo {field} ausente no modal"
    row = re.search(r"<p[^>]*data-field=\"\"[^>]*>", html)
    assert row is not None
    for attribute in ("data-field", "data-old-value", "data-new-value"):
        assert attribute in row.group()


def test_index_page_declares_target_stage_start_from_preview_values() -> None:
    """O início da Etapa alvo declara rótulo canônico e origem dos valores na prévia."""
    html = _html()
    label = re.search(
        r"<span[^>]*data-impact-field=\"target-stage-start\"[^>]*>([^<]*)</span>", html
    )
    assert label is not None
    assert label.group(1).strip() == "Início da Etapa de Viagem alvo"
    assert 'data-impact-source="preview"' in label.group()
    assert 'data-preview-old="old_target_start"' in label.group()
    assert 'data-preview-new="new_target_start"' in label.group()


def test_index_page_declares_ripple_actions_and_persistence_intent() -> None:
    """Os controles declaram ação, endpoint e intenção de persistência da Viagem."""
    html = _html()
    expected = {
        "preview-ripple-shift": ("/api/trip/ripple-shift/preview", None),
        "confirm-ripple-shift": ("/api/trip/ripple-shift/apply", "after-confirm"),
        "close-impact-modal": (None, "never"),
        "export-backup-json": (None, None),
        "restore-backup-json": ("/api/trip/backup/validate", None),
    }
    for action, (endpoint, persistence) in expected.items():
        elements = re.findall(r"<[^>]*\bdata-action=\"" + re.escape(action) + r"\"[^>]*>", html)
        assert elements, f"Nenhum controle declara a ação {action}"
        for element in elements:
            if endpoint is not None:
                assert f'data-endpoint="{endpoint}"' in element
            if persistence is not None:
                assert f'data-persist-trip="{persistence}"' in element
    confirm = element_attributes(html, "modal-confirm-btn")
    assert confirm["data-action"] == "confirm-ripple-shift"
    assert confirm["data-endpoint"] == "/api/trip/ripple-shift/apply"
    for element_id in ("modal-cancel-btn", "modal-close-btn"):
        assert element_attributes(html, element_id)["data-persist-trip"] == "never"


def test_index_page_exposes_json_backup_controls() -> None:
    """A página oferece exportação/restauração de Backup JSON e entrada de arquivo oculta."""
    html = _html()
    assert "Exportar Backup JSON" in html
    assert "Restaurar Backup JSON" in html
    for element_id in (
        "export-backup-json",
        "restore-backup-json",
        "backup-file-input",
    ):
        assert f'id="{element_id}"' in html
    file_input = re.search(r"<input[^>]*id=\"backup-file-input\"[^>]*>", html)
    assert file_input is not None
    assert 'type="file"' in file_input.group()
    assert "hidden" in file_input.group()
    assert element_attributes(html, "restore-backup-json")["data-endpoint"] == (
        "/api/trip/backup/validate"
    )
    assert "kairos_trip_v1" in html
    assert "viagem-kairos.json" in html
    backup_start = html.index('id="trip-backup-controls"')
    backup_section = html[backup_start : html.index("</section>", backup_start)]
    assert "Rota" not in backup_section


def test_index_page_declares_user_facing_error_messages() -> None:
    """As mensagens de erro visíveis são declaradas no HTML e usam o banner de estado."""
    html = _html()
    messages = message_catalog(html)
    assert "A Viagem salva não foi alterada." in messages["previewHttpError"]
    assert "A Viagem salva não foi alterada." in messages["applyHttpError"]
    assert "A Viagem salva não foi alterada." in messages["restoreHttpError"]
    assert "Não foi possível ler o arquivo de Backup JSON" in messages["restoreReadError"]
    assert element_attributes(html, "impact-banner")["role"] == "status"
    assert "alert(" not in html
