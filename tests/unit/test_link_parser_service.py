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
