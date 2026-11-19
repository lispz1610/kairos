from __future__ import annotations

import re
from typing import List, Optional

from src.core.domain.models import POI
from src.core.ports.fetcher import SSRFValidationError, UrlFetcherPort
from src.core.services.curation import CurationService


class LinkParserService:
    """Valida URLs com proteção estrita contra SSRF e extrai estabelecimentos citados."""

    def __init__(
        self,
        fetcher: Optional[UrlFetcherPort] = None,
        curation_service: Optional[CurationService] = None,
    ) -> None:
        self.fetcher = fetcher
        self.curation_service = curation_service or CurationService()

    def validate_url_safety(self, url: str) -> None:
        """Delega a validação da URL à porta de busca configurada."""
        if self.fetcher is None:
            raise RuntimeError("Fetcher não configurado no LinkParserService.")
        self.fetcher.validate_url_safety(url)

    def fetch_url_content(self, url: str) -> str:
        """Busca o conteúdo textual da URL utilizando a porta de busca injetada."""
        if self.fetcher is None:
            raise RuntimeError("Fetcher não configurado no LinkParserService.")
        return self.fetcher.fetch_url(url)

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


__all__ = ["LinkParserService", "SSRFValidationError", "UrlFetcherPort"]
