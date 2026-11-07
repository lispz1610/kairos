from unittest.mock import MagicMock, patch

import pytest

from src.core.services.link_parser import LinkParserService, SSRFValidationError


def test_ssrf_validator_blocks_local_and_private_ips() -> None:
    parser = LinkParserService()

    # Loopback and local IPs must be rejected
    with pytest.raises(SSRFValidationError):
        parser.validate_url_safety("http://localhost:8000/internal-data")

    with pytest.raises(SSRFValidationError):
        parser.validate_url_safety("http://127.0.0.1/admin")

    with pytest.raises(SSRFValidationError):
        parser.validate_url_safety("http://192.168.1.1/router")

    with pytest.raises(SSRFValidationError):
        parser.validate_url_safety("http://10.0.0.5/secrets")

    # Non-http protocols must be rejected
    with pytest.raises(SSRFValidationError):
        parser.validate_url_safety("file:///etc/passwd")

    with pytest.raises(SSRFValidationError):
        parser.validate_url_safety("ftp://example.com/file")

    with pytest.raises(SSRFValidationError, match="URL inválida"):
        parser.validate_url_safety("http://")

    with pytest.raises(SSRFValidationError, match="Falha ao resolver"):
        parser.validate_url_safety("http://non-existent-domain-kairos-test-12345.org")


def test_fetch_url_content_success_and_size_limit() -> None:
    parser = LinkParserService()

    safe_addr = [(None, None, None, None, ("93.184.216.34", 80))]
    with patch("socket.getaddrinfo", return_value=safe_addr):
        # Mock httpx response
        mock_response = MagicMock()
        mock_response.content = b"<html>Sample Article Coffee Lab</html>"
        mock_response.text = "<html>Sample Article Coffee Lab</html>"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client.get", return_value=mock_response):
            content = parser.fetch_url_content("https://example.com/guide")
            assert "Coffee Lab" in content

        # Exceed size limit
        huge_response = MagicMock()
        huge_response.content = b"x" * 1_000_001
        huge_response.raise_for_status = MagicMock()

        with patch("httpx.Client.get", return_value=huge_response):
            with pytest.raises(ValueError, match="limite máximo"):
                parser.fetch_url_content("https://example.com/huge")


def test_text_extraction_identifies_matching_places() -> None:
    parser = LinkParserService()
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
