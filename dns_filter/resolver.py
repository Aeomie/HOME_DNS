"""Synchronous forwarding to configured upstream DNS resolvers."""

from __future__ import annotations

import socket

from .config import CONFIG
from .policy import load_resolvers


class UpstreamResolutionError(RuntimeError):
    """Raised when every configured upstream resolver fails."""


class UpstreamResolver:
    """Forward a complete DNS request and return the upstream response."""

    def __init__(
        self,
        upstreams: list[str] | None = None,
        port: int = 53,
        timeout: float = CONFIG.timeout_seconds,
        resolver_path: str | None = None,
    ) -> None:
        if upstreams is None:
            upstreams = CONFIG.upstreams
        if not upstreams:
            raise ValueError("at least one upstream resolver is required")
        if timeout <= 0:
            raise ValueError("upstream timeout must be greater than zero")
        self.upstreams = list(upstreams)
        self.port = port
        self.timeout = timeout
        self.resolver_path = resolver_path

    def resolve(self, request: bytes) -> bytes:
        """Try each upstream in order and return the first valid response."""
        if len(request) < 2:
            raise ValueError("DNS request must contain a transaction ID")

        transaction_id = request[:2]
        if self.resolver_path is not None:
            try:
                resolvers = load_resolvers(self.resolver_path, self.upstreams)
            except (OSError, ValueError) as exc:
                raise UpstreamResolutionError(
                    f"could not read resolver file: {exc}"
                ) from exc
            self.upstreams = [
                address for address, active in resolvers.items() if active
            ]
        if not self.upstreams:
            raise UpstreamResolutionError("no active upstream resolvers configured")
        failures: list[str] = []

        for upstream in self.upstreams:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                    client.settimeout(self.timeout)
                    client.connect((upstream, self.port))
                    client.send(request)
                    response = client.recv(4096)
            except (OSError, socket.timeout) as exc:
                failures.append(f"{upstream}: {exc}")
                continue

            if len(response) < 2 or response[:2] != transaction_id:
                failures.append(f"{upstream}: response transaction ID mismatch")
                continue
            return response

        raise UpstreamResolutionError(
            "all upstream resolvers failed: " + "; ".join(failures)
        )
