"""Contratos HTTP e de estrutura HTML da interface web (RF06/RF08)."""

import re

import pytest
from fastapi.testclient import TestClient

from src.adapters.web.app import app
from tests.html_contract import element_attributes, message_catalog
from tests.trip_payloads import restorable_trip_payload

client = TestClient(app)


def _html() -> str:
    """Obtém o HTML servido pela página inicial."""
    return client.get("/").text


@pytest.mark.requirement("RF08")
def test_health_check() -> None:
    """Verifica que o endpoint de saúde responde com o status da aplicação."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "kairos"}


@pytest.mark.requirement("RF08")
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


@pytest.mark.requirement("RF06")
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


@pytest.mark.requirement("RF06")
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


@pytest.mark.requirement("RF06")
def test_index_page_declares_target_stage_start_label() -> None:
    """O rótulo do início da Etapa de Viagem alvo é visível no modal."""
    html = _html()
    label = re.search(
        r"<span[^>]*data-impact-field=\"target-stage-start\"[^>]*>([^<]*)</span>", html
    )
    assert label is not None
    assert label.group(1).strip() == "Início da Etapa de Viagem alvo"


@pytest.mark.requirement("RF06")
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


@pytest.mark.requirement("RF08")
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


@pytest.mark.requirement("RF08")
def test_backup_restore_controls_declare_picker_and_change_trigger() -> None:
    """O botão declara o seletor oculto e a escolha de arquivo dispara a restauração."""
    html = _html()
    button = element_attributes(html, "restore-backup-json")
    file_input = element_attributes(html, "backup-file-input")

    assert button["data-action"] == "restore-backup-json"
    assert button["data-file-input-target"] == file_input["id"] == "backup-file-input"
    assert file_input["type"] == "file"
    file_input_tag = re.search(r"<input[^>]*id=\"backup-file-input\"[^>]*>", html)
    assert file_input_tag is not None
    assert "hidden" in file_input_tag.group()
    assert file_input["accept"] == "application/json,.json"
    assert (
        re.search(
            r'<button[^>]*id="restore-backup-json"[^>]*>\s*Restaurar Backup JSON\s*</button>',
            html,
        )
        is not None
    )


@pytest.mark.requirement("RF08")
def test_backup_restore_success_contract_uses_validated_trip_and_render_targets() -> None:
    """Só a Viagem validada com 200 alimenta o armazenamento e o resumo/selector."""
    html = _html()
    button = element_attributes(html, "restore-backup-json")
    assert button["data-persist-trip"] == "after-validate"

    response = client.post(button["data-endpoint"], json=restorable_trip_payload())

    assert response.status_code == 200, response.text
    validated = response.json()
    assert [stage["city_name"] for stage in validated["stages"]] == ["São Paulo", "Lima"]
    assert [stage["id"] for stage in validated["stages"]] == ["stage-sp", "stage-lima"]
    assert all(stage["days"] for stage in validated["stages"])
    assert element_attributes(html, "trip-planning")["data-trip-storage-key"] == ("kairos_trip_v1")
    assert element_attributes(html, "trip-stages")["data-role"] == "trip-stage-summary"
    assert element_attributes(html, "stage-selector")["aria-label"] == "Etapa de Viagem"


@pytest.mark.requirement("RF08")
def test_backup_restore_failure_contract_keeps_trip_and_reports_in_banner() -> None:
    """Falhas de leitura, JSON, rede e validação são comunicadas sem tocar a Viagem."""
    html = _html()
    button = element_attributes(html, "restore-backup-json")

    rejected = client.post(button["data-endpoint"], json={"title": "Viagem sem id"})

    assert rejected.status_code == 422
    assert rejected.json()["detail"]
    messages = message_catalog(html)
    for key in (
        "restoreNoFile",
        "restoreReadError",
        "restoreParseError",
        "restoreNetworkError",
        "restoreHttpError",
    ):
        assert "Backup JSON" in messages[key], key
        assert "A Viagem salva não foi alterada." in messages[key], key
    assert "{status}" in messages["restoreHttpError"]
    assert element_attributes(html, "impact-banner")["role"] == "status"


@pytest.mark.requirement("RF06", "RF08")
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


@pytest.mark.requirement("RF12", "RF13")
def test_replan_request_sends_future_reserved_stops_from_day_state() -> None:
    """A interface envia paradas futuras reservadas ao endpoint de Replanejamento."""
    html = _html()
    assert "reserved_future_stops: state.reserved_future_stops || []" in html


@pytest.mark.requirement("RF03", "RF13")
def test_replan_request_reads_future_meal_slots_from_trip_day() -> None:
    """A requisição usa Slots de Refeição do Dia de Viagem salvo."""
    html = _html()
    assert "reserved_meal_slots: futureMealSlots(state)" in html
    assert "function futureMealSlots(state)" in html
    assert "const trip = loadTrip();" in html


@pytest.mark.requirement("RF08", "RF13")
def test_replan_saves_effective_itinerary_in_trip_day_for_export() -> None:
    """O guia da Viagem usa o Roteiro persistido após o Replanejamento."""
    html = _html()
    assert "day.itinerary = { stops: data.itinerary };" in html
    assert "saveTrip(trip);" in html
