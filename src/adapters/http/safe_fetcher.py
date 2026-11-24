from __future__ import annotations

import ipaddress
import socket
from typing import Iterable, Optional, Tuple
from urllib.parse import ParseResult, urlparse

import httpcore
import httpx

from src.core.ports.fetcher import SSRFValidationError, UrlFetcherPort

# Denylist usada na validação anti-SSRF; "0.0.0.0" não é endereço de bind
# (B104 excluído no gate: bandit -s B104).
FORBIDDEN_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})
UNSAFE_IP_CHECKS = (
    "is_private",
    "is_loopback",
    "is_link_local",
    "is_reserved",
    "is_multicast",
    "is_unspecified",
)


class PinnedIPBackend(httpcore.SyncBackend):
    """Network backend que direciona conexões TCP diretamente ao IP já validado."""

    def __init__(self, pinned_ip: str) -> None:
        """Inicializa o backend fixando o endereço IP alvo das conexões TCP."""
        super().__init__()
        self.pinned_ip = pinned_ip

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Iterable[httpcore.SOCKET_OPTION]] = None,
    ) -> httpcore.NetworkStream:
        """Conecta no IP fixado em vez do hostname, prevenindo DNS rebinding."""
        return super().connect_tcp(
            host=self.pinned_ip,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


class PinnedIPTransport(httpx.HTTPTransport):
    """Transporte HTTP com pinning de endereço IP para prevenir TOCTOU / DNS rebinding."""

    def __init__(self, pinned_ip: str, **kwargs: object) -> None:
        """Inicializa o transporte substituindo o pool padrão por um backend com IP fixado."""
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._pool = httpcore.ConnectionPool(
            ssl_context=self._pool._ssl_context,
            network_backend=PinnedIPBackend(pinned_ip),
        )


class SafeHttpFetcher(UrlFetcherPort):
    """Adaptador HTTP com validação anti-SSRF e mitigação de TOCTOU / DNS rebinding."""

    def __init__(
        self,
        timeout: float = 5.0,
        max_content_bytes: int = 1_000_000,
        user_agent: str = "Kairos-Curation-Bot/1.0",
    ) -> None:
        """Configura timeout, limite de conteúdo e user-agent da porta UrlFetcherPort anti-SSRF."""
        self.timeout = timeout
        self.max_content_bytes = max_content_bytes
        self.user_agent = user_agent

    def validate_url_safety(self, url: str) -> None:
        """Valida que a URL não viola políticas anti-SSRF."""
        self._resolve_and_validate(url)

    def _check_ip_safety(self, ip_str: str) -> None:
        """Garante que um endereço IP não pertença a faixas privadas, loopback ou reservadas."""
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError as err:
            raise SSRFValidationError(f"Endereço IP inválido '{ip_str}': {err}")

        if any(getattr(ip_obj, attr, False) for attr in UNSAFE_IP_CHECKS):
            raise SSRFValidationError(
                f"Endereço IP '{ip_str}' reside em faixa privada ou restrita."
            )

    def _validate_url_components(self, parsed: ParseResult) -> Tuple[str, int]:
        """Valida esquema, presença de hostname e hostnames proibidos."""
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            raise SSRFValidationError(
                f"Protocolo '{parsed.scheme}' não autorizado. Utilize apenas HTTP ou HTTPS."
            )

        hostname = parsed.hostname
        if not hostname:
            raise SSRFValidationError("URL inválida: nome de host ausente.")

        if hostname.lower() in FORBIDDEN_HOSTNAMES:
            raise SSRFValidationError("Acesso a loopback/localhost é proibido (SSRF).")

        port = parsed.port or (443 if scheme == "https" else 80)
        return hostname, port

    def _resolve_dns_ips(self, hostname: str, port: int) -> list[str]:
        """Resolve o hostname via DNS e retorna os endereços IP como strings."""
        try:
            addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except socket.gaierror as err:
            raise SSRFValidationError(f"Falha ao resolver nome de host '{hostname}': {err}")

        if not addr_info:
            raise SSRFValidationError(
                f"Falha ao resolver nome de host '{hostname}': nenhum endereço retornado."
            )

        ips: list[str] = []
        for item in addr_info:
            ip_str = str(item[4][0])
            if ip_str not in ips:
                ips.append(ip_str)
        return ips

    def _resolve_and_validate(self, url: str) -> Tuple[str, int]:
        """Analisa a URL, resolve o DNS uma única vez e valida todos os endereços IP."""
        parsed = urlparse(url)
        hostname, port = self._validate_url_components(parsed)
        resolved_ips = self._resolve_dns_ips(hostname, port)

        for ip_str in resolved_ips:
            self._check_ip_safety(ip_str)

        return resolved_ips[0], port

    def fetch_url(self, url: str) -> str:
        """Busca o conteúdo textual de uma URL utilizando transporte com IP pinning."""
        pinned_ip, _ = self._resolve_and_validate(url)
        transport = PinnedIPTransport(pinned_ip=pinned_ip)

        with httpx.Client(
            transport=transport,
            timeout=self.timeout,
            follow_redirects=False,
        ) as client:
            resp = client.get(url, headers={"User-Agent": self.user_agent})
            if 300 <= resp.status_code < 400:
                raise SSRFValidationError(
                    f"Redirecionamento não permitido (status {resp.status_code})."
                )
            resp.raise_for_status()
            if len(resp.content) > self.max_content_bytes:
                raise ValueError("O conteúdo da página excede o limite máximo permitido de 1 MB.")
            return resp.text
