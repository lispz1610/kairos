from fastapi.testclient import TestClient

from src.adapters.web.app import app

client = TestClient(app)


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
