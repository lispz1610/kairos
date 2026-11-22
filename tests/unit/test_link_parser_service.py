from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.adapters.http.safe_fetcher import (
    PinnedIPBackend,
    PinnedIPTransport,
    SafeHttpFetcher,
)
from src.adapters.places import OfflineReplayPlacesAdapter
from src.core.ports.fetcher import SSRFValidationError, UrlFetcherPort
from src.core.services.link_parser import LinkParserService

# ---------------------------------------------------------------------------
# Decoupling & Unit Tests for LinkParserService
# ---------------------------------------------------------------------------


def test_link_parser_service_requires_fetcher_for_network_calls() -> None:
    """Verifica que operações de rede falham sem um buscador configurado."""
    parser = LinkParserService(fetcher=None)

    with pytest.raises(RuntimeError, match="Fetcher não configurado"):
        parser.validate_url_safety("https://example.com")

    with pytest.raises(RuntimeError, match="Fetcher não configurado"):
        parser.fetch_url_content("https://example.com")


def test_link_parser_service_delegates_to_fetcher_port() -> None:
    """Verifica que o serviço delega validação e busca à porta de busca."""
    mock_fetcher = MagicMock(spec=UrlFetcherPort)
    mock_fetcher.fetch_url.return_value = "<html>Content with Coffee Lab</html>"

    parser = LinkParserService(fetcher=mock_fetcher)
    parser.validate_url_safety("https://example.com/guide")
    mock_fetcher.validate_url_safety.assert_called_once_with("https://example.com/guide")

    content = parser.fetch_url_content("https://example.com/guide")
    assert content == "<html>Content with Coffee Lab</html>"
    mock_fetcher.fetch_url.assert_called_once_with("https://example.com/guide")


# ---------------------------------------------------------------------------
# Parametrized SSRF Rejection Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_url, expected_error_fragment",
    [
        # Esquemas inválidos / não autorizados
        ("file:///etc/passwd", "não autorizado"),
        ("ftp://example.com/file", "não autorizado"),
        ("gopher://example.com/1", "não autorizado"),
        # Host ausente / vazio
        ("http://", "URL inválida: nome de host ausente"),
        ("https://", "URL inválida: nome de host ausente"),
        # Loopback e localhost
        ("http://localhost:8000/internal-data", "loopback/localhost é proibido"),
        ("http://127.0.0.1/admin", "loopback/localhost é proibido"),
        ("http://0.0.0.0/test", "loopback/localhost é proibido"),
        ("http://[::1]/secret", "loopback/localhost é proibido"),
        # Faixas de IP privadas (RFC 1918)
        ("http://192.168.1.1/router", "faixa privada ou restrita"),
        ("http://10.0.0.5/secrets", "faixa privada ou restrita"),
        ("http://172.16.0.1/internal", "faixa privada ou restrita"),
        # Faixa link-local e cloud metadata (169.254.x.x)
        ("http://169.254.169.254/latest/meta-data", "faixa privada ou restrita"),
        # Falha de resolução DNS
        ("http://non-existent-domain-kairos-test-12345.org", "Falha ao resolver"),
    ],
)
def test_ssrf_validator_blocks_forbidden_urls(
    invalid_url: str, expected_error_fragment: str
) -> None:
    """Verifica que o validador SSRF rejeita URLs proibidas com a mensagem esperada."""
    fetcher = SafeHttpFetcher()
    parser = LinkParserService(fetcher=fetcher)

    with pytest.raises(SSRFValidationError, match=expected_error_fragment):
        parser.validate_url_safety(invalid_url)


# ---------------------------------------------------------------------------
# Parametrized Simulation of Valid Content Fetching
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, mock_html, expected_snippet",
    [
        (
            "https://example.com/guide",
            "<html><h1>Guia de SP</h1><p>Visite o Coffee Lab hoje.</p></html>",
            "Coffee Lab",
        ),
        (
            "http://travelblog.org/destinos/lima",
            "<div>Restaurantes recomendados: Central e Maido.</div>",
            "Central",
        ),
    ],
)
def test_fetch_url_content_valid_simulation(
    url: str, mock_html: str, expected_snippet: str
) -> None:
    """Verifica que o conteúdo buscado contém o trecho esperado."""
    fetcher = SafeHttpFetcher()
    parser = LinkParserService(fetcher=fetcher)

    safe_addr = [(None, None, None, None, ("93.184.216.34", 80))]
    with patch("socket.getaddrinfo", return_value=safe_addr):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = mock_html.encode("utf-8")
        mock_response.text = mock_html
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client.get", return_value=mock_response):
            content = parser.fetch_url_content(url)
            assert expected_snippet in content


def test_fetch_url_content_size_limit_exceeded() -> None:
    """Verifica que conteúdo acima do limite máximo é rejeitado."""
    fetcher = SafeHttpFetcher(max_content_bytes=1_000_000)
    parser = LinkParserService(fetcher=fetcher)

    safe_addr = [(None, None, None, None, ("93.184.216.34", 80))]
    with patch("socket.getaddrinfo", return_value=safe_addr):
        huge_response = MagicMock()
        huge_response.status_code = 200
        huge_response.content = b"x" * 1_000_001
        huge_response.text = "x" * 1_000_001
        huge_response.raise_for_status = MagicMock()

        with patch("httpx.Client.get", return_value=huge_response):
            with pytest.raises(ValueError, match="limite máximo"):
                parser.fetch_url_content("https://example.com/huge")


# ---------------------------------------------------------------------------
# DNS Rebinding (TOCTOU) & Security Tests
# ---------------------------------------------------------------------------


def test_dns_rebinding_simulation_dual_homed_host_is_rejected() -> None:
    """Se o DNS responder com múltiplos IPs e um deles for privado, deve rejeitar."""
    fetcher = SafeHttpFetcher()
    parser = LinkParserService(fetcher=fetcher)

    # DNS retorna IP público E IP privado (tentativa de DNS rebinding)
    mixed_addr = [
        (None, None, None, None, ("93.184.216.34", 80)),
        (None, None, None, None, ("127.0.0.1", 80)),
    ]
    with patch("socket.getaddrinfo", return_value=mixed_addr):
        with pytest.raises(SSRFValidationError, match="faixa privada ou restrita"):
            parser.validate_url_safety("https://rebound-attack.example.com")


def test_dns_rebinding_ip_pinning_transport_connects_only_to_validated_ip() -> None:
    """Garante que o transporte HTTP conecta exclusivamente ao IP validado (sem re-resolução)."""
    pinned_ip = "93.184.216.34"
    backend = PinnedIPBackend(pinned_ip=pinned_ip)

    with patch("httpcore.SyncBackend.connect_tcp") as mock_super_connect:
        mock_super_connect.return_value = MagicMock()

        # Chama connect_tcp passando hostname como 'rebound-domain.com'
        backend.connect_tcp(
            host="rebound-domain.com",
            port=443,
            timeout=5.0,
            local_address=None,
            socket_options=None,
        )

        # O host passado à conexão física DEVE ser estritamente o IP pinned
        mock_super_connect.assert_called_once_with(
            host=pinned_ip,
            port=443,
            timeout=5.0,
            local_address=None,
            socket_options=None,
        )


def test_pinned_ip_transport_initializes_with_backend() -> None:
    """Verifica que o transporte usa o backend de IP fixado."""
    transport = PinnedIPTransport(pinned_ip="93.184.216.34")
    assert transport._pool is not None
    assert isinstance(transport._pool._network_backend, PinnedIPBackend)
    assert transport._pool._network_backend.pinned_ip == "93.184.216.34"


def test_fetch_url_rejects_http_redirects() -> None:
    """Redirecionamentos 3xx devem ser rejeitados para evitar desvio para destinos internos."""
    fetcher = SafeHttpFetcher()

    safe_addr = [(None, None, None, None, ("93.184.216.34", 80))]
    with patch("socket.getaddrinfo", return_value=safe_addr):
        redirect_resp = MagicMock()
        redirect_resp.status_code = 302
        redirect_resp.headers = {"Location": "http://127.0.0.1:8000/internal"}

        with patch("httpx.Client.get", return_value=redirect_resp):
            with pytest.raises(SSRFValidationError, match="Redirecionamento não permitido"):
                fetcher.fetch_url("https://example.com/redirect-to-internal")


# ---------------------------------------------------------------------------
# Text Extraction Test (Business Logic)
# ---------------------------------------------------------------------------


def test_link_parser_service_requires_curation_service_for_extraction() -> None:
    """Verifica que a extração falha sem CurationService ou PlacesPort configurados."""
    parser = LinkParserService()

    with pytest.raises(RuntimeError, match="CurationService não configurado"):
        parser.extract_places_from_text("Coffee Lab em São Paulo")


def test_text_extraction_identifies_matching_places() -> None:
    """Verifica a extração de Pontos de Interesse mencionados em texto livre."""
    parser = LinkParserService(places_port=OfflineReplayPlacesAdapter())
    sample_article = """
    Guia de São Paulo:
    Não deixe de visitar o Coffee Lab na Vila Madalena para provar cafés incríveis.
    Para jantar, o icônico D.O.M. do chef Alex Atala oferece uma experiência inesquecível.
    Outra parada obrigatória é o MASP na Avenida Paulista.
    """

    candidates = parser.extract_places_from_text(sample_article, city_name="São Paulo")
    names = [c.name for c in candidates]

    assert any("Coffee Lab" in n for n in names)
    assert any("D.O.M." in n for n in names)
