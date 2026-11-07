from fastapi.testclient import TestClient

from src.adapters.web.app import app

client = TestClient(app)


def test_import_link_ssrf_protection_returns_400() -> None:
    # Attempting to scan loopback
    response = client.post(
        "/api/curation/import-link",
        json={"url": "http://127.0.0.1:8000/secrets", "city_name": "São Paulo"},
    )
    assert response.status_code == 400
    assert "SSRF" in response.json()["detail"] or "privado" in response.json()["detail"]


def test_import_link_with_raw_text_succeeds() -> None:
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
