from __future__ import annotations

import ipaddress
import re
import socket
from typing import List, Optional
from urllib.parse import urlparse

import httpx

from src.core.domain.models import POI
from src.core.ports.places import PlacesPort
from src.core.services.curation import CurationService


class SSRFValidationError(Exception):
    """Exceção levantada quando uma URL tenta acessar rede interna ou IP restrito."""

    pass


class LinkParserService:
    """Valida URLs com proteção estrita contra SSRF e extrai estabelecimentos citados."""

    def __init__(
        self,
        curation_service: Optional[CurationService] = None,
        places_port: Optional[PlacesPort] = None,
    ) -> None:
        if curation_service is not None:
            self.curation_service = curation_service
        elif places_port is not None:
            self.curation_service = CurationService(places_port=places_port)
        else:
            self.curation_service = CurationService()

    def validate_url_safety(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            raise SSRFValidationError(
                f"Protocolo '{parsed.scheme}' não autorizado. Utilize apenas HTTP ou HTTPS."
            )

        hostname = parsed.hostname
        if not hostname:
            raise SSRFValidationError("URL inválida: nome de host ausente.")

        if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            raise SSRFValidationError("Acesso a loopback/localhost é proibido (SSRF).")

        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for item in addr_info:
                self._check_ip_safety(str(item[4][0]))
        except socket.gaierror as err:
            raise SSRFValidationError(f"Falha ao resolver nome de host '{hostname}': {err}")

    def _check_ip_safety(self, ip_str: str) -> None:
        ip_obj = ipaddress.ip_address(ip_str)
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
        ):
            raise SSRFValidationError(
                f"Endereço IP '{ip_str}' reside em faixa privada ou restrita."
            )

    def fetch_url_content(self, url: str) -> str:
        self.validate_url_safety(url)
        with httpx.Client(timeout=5.0, follow_redirects=False) as client:
            resp = client.get(url, headers={"User-Agent": "Kairos-Curation-Bot/1.0"})
            resp.raise_for_status()
            # Limite de segurança de 1 MB
            if len(resp.content) > 1_000_000:
                raise ValueError("O conteúdo da página excede o limite máximo permitido de 1 MB.")
            return resp.text

    def extract_places_from_text(
        self, text: str, city_name: Optional[str] = None
    ) -> List[POI]:
        candidates: List[POI] = []
        found_ids: set[str] = set()

        # Extrai potenciais nomes próprios em maiúsculas (ex: "Coffee Lab", "D.O.M.", "Central")
        pattern = r"\b[A-Z][A-Za-z0-9\.\'\-]{1,20}(?:\s+[A-Z][A-Za-z0-9\.\'\-]{1,20})*\b"
        tokens = re.findall(pattern, text)

        for token in tokens:
            if len(token) < 3:
                continue
            matched = self.curation_service.search_places_autocomplete(token, city_name)
            for poi in matched:
                if poi.id not in found_ids:
                    found_ids.add(poi.id)
                    candidates.append(poi)

        return candidates[:8]
