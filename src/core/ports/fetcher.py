from __future__ import annotations

from abc import ABC, abstractmethod


class SSRFValidationError(Exception):
    """Exceção levantada quando uma URL tenta acessar rede interna ou IP restrito."""

    pass


class UrlFetcherPort(ABC):
    """Porta hexagonal abstrata para busca de URLs externas."""

    @abstractmethod
    def fetch_url(self, url: str) -> str:
        """Busca o conteúdo textual de uma URL com validação de segurança."""
        raise NotImplementedError

    @abstractmethod
    def validate_url_safety(self, url: str) -> None:
        """Valida que a URL não viola políticas de segurança anti-SSRF."""
        raise NotImplementedError
