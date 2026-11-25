from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.adapters.places.cached_adapter import CachedPlacesAdapter
from src.adapters.web import app as web_module
from src.core.services.curation import CurationService

client = TestClient(web_module.app)


@pytest.fixture(autouse=True)
def isolated_places_adapter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Isolar o cache SQLite durante os testes de importação de link."""
    adapter = CachedPlacesAdapter(api_key="", cache_path=tmp_path / "places.db")
    service = CurationService(places_port=adapter)
    monkeypatch.setattr(web_module, "places_adapter", adapter)
    monkeypatch.setattr(web_module, "curation_service", service)
    monkeypatch.setattr(web_module.link_parser_service, "curation_service", service)
    yield
    adapter._conn.close()


@pytest.mark.parametrize(
    "forbidden_url",
    [
        "http://127.0.0.1:8000/secrets",
        "http://localhost:9000/admin",
        "http://192.168.0.1/config",
        "http://10.0.0.1/keys",
        "file:///etc/shadow",
    ],
)
@pytest.mark.requirement("RF05")
def test_import_link_ssrf_protection_returns_400(forbidden_url: str) -> None:
    """Verifica que URLs proibidas por SSRF são rejeitadas com 400."""
    response = client.post(
        "/api/curation/import-link",
        json={"url": forbidden_url, "city_name": "São Paulo"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert any(
        kw in detail.lower()
        for kw in ("ssrf", "privad", "loopback", "proibido", "não autorizado")
    )


@pytest.mark.requirement("RF05")
def test_import_link_with_raw_text_succeeds() -> None:
    """Verifica a extração de candidatos a partir de texto livre."""
    text_payload = {
        "text": "Adoramos o Central em Lima e o Maido, ambos extraordinários!",
        "city_name": "Lima",
    }
    response = client.post("/api/curation/import-link", json=text_payload)
    assert response.status_code == 200
    data = response.json()
    assert "candidates" in data
    names = [c["name"] for c in data["candidates"]]
    assert any("Central" in n for n in names)


@pytest.mark.requirement("RF05")
def test_import_link_with_valid_url_succeeds() -> None:
    """Verifica a extração de candidatos a partir de uma URL segura."""
    safe_addr = [(None, None, None, None, ("93.184.216.34", 80))]
    with patch("socket.getaddrinfo", return_value=safe_addr):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<html>Conheca o Coffee Lab e o D.O.M. em SP</html>"
        mock_response.text = "<html>Conheca o Coffee Lab e o D.O.M. em SP</html>"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client.get", return_value=mock_response):
            response = client.post(
                "/api/curation/import-link",
                json={"url": "https://example.com/sp-guide", "city_name": "São Paulo"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "candidates" in data
            names = [c["name"] for c in data["candidates"]]
            assert any("Coffee Lab" in n for n in names)
