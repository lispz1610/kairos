import re

from fastapi.testclient import TestClient

from src.adapters.web.app import app

client = TestClient(app)


def _script_function_body(html: str, name: str) -> str:
    """Extrai o corpo de uma função JavaScript declarada no HTML servido."""
    match = re.search(
        r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{(?P<body>[\s\S]*?)\n\}",
        html,
    )
    assert match is not None, f"Função JavaScript {name} não encontrada no HTML"
    return match.group("body")


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
    html = client.get("/").text
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
    """Verifica o resumo das Etapas de Viagem, o seletor e o delta numérico na página."""
    html = client.get("/").text
    assert 'id="trip-planning"' in html
    assert "Planejamento da Viagem" in html
    assert 'id="trip-stages"' in html
    assert 'id="stage-selector"' in html
    assert 'id="delta-days" type="number"' in html
    assert 'id="preview-ripple-shift"' in html
    assert "kairos_trip_v1" in html


def test_index_page_exposes_impact_confirmation_modal() -> None:
    """Verifica o modal com datas anteriores e recalculadas e a prévia via API."""
    html = client.get("/").text
    for element_id in (
        "modal-overlay",
        "modal-title",
        "modal-body",
        "modal-impact-list",
        "modal-cancel-btn",
        "modal-close-btn",
    ):
        assert f'id="{element_id}"' in html
    assert "Modal de Confirmação de Impacto" in html
    assert "Datas anteriores" in html
    assert "Datas recalculadas" in html
    assert "Etapas de Viagem" in html
    assert "Conexões Interurbanas" in html
    assert "/api/trip/ripple-shift/preview" in html
    assert "A prévia do Deslocamento em Cascata falhou" in html
    assert "showError(" in html
    assert "alert(" not in html


def test_index_page_wires_ripple_apply() -> None:
    """Verifica que Confirmar aplica a prévia, persiste a Viagem e atualiza o resumo."""
    html = client.get("/").text
    assert 'id="modal-confirm-btn"' in html
    assert 'addEventListener("click", confirmRippleShift)' in html
    assert '"/api/trip/ripple-shift/apply"' in html

    body = _script_function_body(html, "confirmRippleShift")
    assert "if (!response.ok)" in body
    assert "saveTrip(updatedTrip)" in body
    assert "renderTripStages(updatedTrip)" in body
    assert "renderStageSelector(updatedTrip" in body
    assert "closeImpactModal()" in body
    assert body.index("if (!response.ok)") < body.index("saveTrip(")


def test_index_page_reports_ripple_apply_failure_without_writing() -> None:
    """Verifica que rejeição na aplicação usa o banner e não grava nem no cancelamento."""
    html = client.get("/").text
    body = _script_function_body(html, "confirmRippleShift")
    assert "showError(" in body
    assert "A aplicação do Deslocamento em Cascata falhou" in body
    assert "A Viagem salva não foi alterada" in body
    assert body.index("showError(") < body.index("saveTrip(")

    close_body = _script_function_body(html, "closeImpactModal")
    assert "saveTrip" not in close_body
    assert "localStorage" not in close_body
    assert html.count('addEventListener("click", closeImpactModal)') == 2


def test_index_page_posts_previewed_stage_and_delta_on_confirm() -> None:
    """Verifica que Confirmar reenvia exatamente a Viagem, a Etapa e o delta pré-visualizados."""
    html = client.get("/").text
    preview_body = _script_function_body(html, "showImpactModal")
    assert "pendingRippleShift = {" in preview_body
    assert "targetStageId: preview.target_stage_id" in preview_body
    assert "deltaDays: preview.delta_days" in preview_body
    assert 'document.getElementById("modal-confirm-btn").disabled = false' in preview_body

    apply_body = _script_function_body(html, "confirmRippleShift")
    assert "trip: requested.trip" in apply_body
    assert "target_stage_id: requested.targetStageId" in apply_body
    assert "delta_days: requested.deltaDays" in apply_body


def test_index_page_refreshes_stage_summary_and_selection_after_apply() -> None:
    """Verifica que o resumo recalcula Etapas, Dias de Viagem e Conexões Interurbanas."""
    html = client.get("/").text
    stages_body = _script_function_body(html, "renderTripStages")
    assert "trip.stages.forEach" in stages_body
    assert "stage.days.forEach" in stages_body
    assert "dayIndex + 1" in stages_body
    assert "formatDate(day.date)" in stages_body
    assert "trip.connections.forEach" in stages_body
    assert "Conexão Interurbana" in stages_body
    assert "connectionDepartureDate(connection)" in stages_body

    selector_body = _script_function_body(html, "renderStageSelector")
    assert "selectedStageId" in selector_body
    assert "selector.value" in selector_body


def test_index_page_exposes_json_backup_controls() -> None:
    """A página oferece exportação/restauração de Backup JSON e entrada de arquivo oculta."""
    html = client.get("/").text
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
    assert "/api/trip/backup/validate" in html
    assert "kairos_trip_v1" in html
    assert "viagem-kairos.json" in html
    backup_start = html.index('id="trip-backup-controls"')
    backup_section = html[backup_start : html.index("</section>", backup_start)]
    assert "Rota" not in backup_section


def test_index_page_backup_flow_validates_before_replacing_trip() -> None:
    """O fluxo de Backup JSON usa validação do backend e banner para recusar arquivos."""
    html = client.get("/").text
    for helper in ("exportTripBackup", "restoreTripBackup", "renderTripStages"):
        assert f"function {helper}(" in html
    assert "JSON.parse(" in html
    assert "response.ok" in html
    assert "Não foi possível restaurar o Backup JSON" in html
    assert "A Viagem salva não foi alterada." in html
    assert "alert(" not in html
