"""Synchronous forwarding to configured upstream DNS resolvers."""

from __future__ import annotations

import socket


DEFAULT_UPSTREAMS = ("1.1.1.1", "8.8.8.8")


class UpstreamResolutionError(RuntimeError):
    """Raised when every configured upstream resolver fails."""


class UpstreamResolver:
    """Forward a complete DNS request and return the upstream response."""

    def __init__(
        self,
        upstreams: tuple[str, ...] = DEFAULT_UPSTREAMS,
        port: int = 53,
        timeout: float = 2.0,
    ) -> None:
        if not upstreams:
            raise ValueError("at least one upstream resolver is required")
        if timeout <= 0:
            raise ValueError("upstream timeout must be greater than zero")
        self.upstreams = upstreams
        self.port = port
        self.timeout = timeout

    def resolve(self, request: bytes) -> bytes:
        """Try each upstream in order and return the first valid response."""
        if len(request) < 2:
            raise ValueError("DNS request must contain a transaction ID")

        transaction_id = request[:2]
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
