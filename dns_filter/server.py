"""Synchronous UDP DNS request inspector for the first project milestone."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from .config import CONFIG
import socket
import threading
from threading import RLock

from .website.main import create_app
from .website.state import DashboardState
from .packet import (
    DNSPacketError,
    build_a_response,
    build_nxdomain_response,
    parse_header,
    parse_question,
)
from .resolver import UpstreamResolutionError, UpstreamResolver
from .policy import load_allowed_records, load_blocklist, list_signature

LOGGER = logging.getLogger(__name__)


class UDPParser:
    """Receive DNS requests, apply local policy, and forward allowed queries."""

    
    
    def __init__(
        self,
        host: str = CONFIG.listen.host,
        port: int = CONFIG.listen.port,
        resolver: UpstreamResolver | None = None,
        local_records: dict[str, str] | None = None,
        blocked_domains: set[str] | None = None,
        blocked_lists_dir: str | Path | None = None,
        allowed_lists_dir: str | Path | None = None,
        dashboard_state: DashboardState | None = None,
    ) -> None:
        """
        host : localhost by default
        port : By default it should be 53 but for testing purposes we will use 5353
        """
        self.address = (host, port)
        self.resolver = resolver or UpstreamResolver()
        self.local_records = local_records or {}
        self.blocked_domains = blocked_domains or set()
        self.blocked_lists_dir = Path(blocked_lists_dir) if blocked_lists_dir else None
        self.allowed_lists_dir = Path(allowed_lists_dir) if allowed_lists_dir else None
        self._policy_signatures: dict[Path, tuple] = {}
        self._policy_lock = RLock()
        self.dashboard_state = dashboard_state
        self._remember_policy_signatures()

    def _remember_policy_signatures(self) -> None:
        for directory in (self.blocked_lists_dir, self.allowed_lists_dir):
            if directory is not None:
                self._policy_signatures[directory] = list_signature(directory)

    def _refresh_policy_files(self) -> None:
        """Reload changed list folders while keeping the server running."""
        with self._policy_lock:
            if self.blocked_lists_dir is not None:
                signature = list_signature(self.blocked_lists_dir)
                if self._policy_signatures.get(self.blocked_lists_dir) != signature:
                    self.blocked_domains = load_blocklist(self.blocked_lists_dir)
                    self._policy_signatures[self.blocked_lists_dir] = signature
                    LOGGER.info("reloaded blocked lists from %s", self.blocked_lists_dir)

            if self.allowed_lists_dir is not None:
                signature = list_signature(self.allowed_lists_dir)
                if self._policy_signatures.get(self.allowed_lists_dir) != signature:
                    self.local_records = load_allowed_records(self.allowed_lists_dir)
                    self._policy_signatures[self.allowed_lists_dir] = signature
                    LOGGER.info("reloaded allowed lists from %s", self.allowed_lists_dir)

    def policy_snapshot(self) -> tuple[set[str], dict[str, str]]:
        self._refresh_policy_files()
        with self._policy_lock:
            return set(self.blocked_domains), dict(self.local_records)

    def serve_forever(self) -> None:
        """
        Listen for DNS requests and log their questions.
        UDP = SOCK DGRAM
        AF_INET = IPv4
        """
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
            server_socket.bind(self.address)
            LOGGER.info("listening for DNS requests on %s:%d", *self.address)

            while True:
                data, client_address = server_socket.recvfrom(4096)
                try:
                    self._refresh_policy_files()
                except (OSError, ValueError) as exc:
                    LOGGER.error("could not refresh DNS policy files: %s", exc)
                LOGGER.info(
                    "received UDP datagram from %s:%d (%d bytes)",
                    client_address[0],
                    client_address[1],
                    len(data),
                )
                try:
                    header = parse_header(data)
                    question = parse_question(data, header)
                except DNSPacketError as exc:
                    LOGGER.warning(
                        "ignoring malformed DNS request from %s: %s",
                        client_address[0],
                        exc,
                    )
                    continue

                LOGGER.info(
                    "DNS query client=%s domain=%s type=%d class=%d",
                    client_address[0],
                    question.domain,
                    question.query_type,
                    question.query_class,
                )
                if question.domain in self.blocked_domains:
                    if self.dashboard_state is not None:
                        self.dashboard_state.record_blocked(
                            question.domain,
                            client_address[0],
                            question.query_type,
                        )
                    server_socket.sendto(build_nxdomain_response(data), client_address)
                    LOGGER.info("blocked DNS query for %s", question.domain)
                    continue

                local_address = self.local_records.get(question.domain)
                if local_address is not None and question.query_type == 1:
                    try:
                        response = build_a_response(data, local_address)
                    except DNSPacketError as exc:
                        LOGGER.warning("could not answer local record for %s: %s", question.domain, exc)
                        continue
                    server_socket.sendto(response, client_address)
                    LOGGER.info("returned local record %s -> %s", question.domain, local_address)
                    continue
                try:
                    response = self.resolver.resolve(data)
                except UpstreamResolutionError as exc:
                    LOGGER.error(
                        "upstream resolution failed for %s: %s",
                        question.domain,
                        exc,
                    )
                    continue

                server_socket.sendto(response, client_address)
                LOGGER.info(
                    "returned %d-byte upstream response for %s",
                    len(response),
                    question.domain,
                )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=CONFIG.listen.host)
    parser.add_argument("--port", type=int, default=CONFIG.listen.port)
    parser.add_argument(
        "--upstream",
        action="append",
        dest="upstreams",
        choices=None,
        help=(
            "upstream DNS IPv4 address; repeat to set order "
            f"(default: {', '.join(CONFIG.upstreams)})"
        ),
    )
    parser.add_argument("--timeout", type=float, default=CONFIG.timeout_seconds)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    resolver = UpstreamResolver(
        upstreams=args.upstreams or CONFIG.upstreams,
        timeout=args.timeout,
        resolver_path=CONFIG.resolvers_path,
    )
    blocked_domains = load_blocklist(CONFIG.blocked_lists_dir)
    local_records = load_allowed_records(CONFIG.allowed_lists_dir)
    dashboard_state = DashboardState()
    dns_server = UDPParser(
        args.host,
        args.port,
        resolver,
        local_records,
        blocked_domains,
        CONFIG.blocked_lists_dir,
        CONFIG.allowed_lists_dir,
        dashboard_state,
    )
    dashboard_app = create_app(dns_server.policy_snapshot, dashboard_state)
    import uvicorn

    dashboard_thread = threading.Thread(
        target=uvicorn.run,
        args=(dashboard_app,),
        kwargs={
            "host": CONFIG.dashboard.host,
            "port": CONFIG.dashboard.port,
            "log_level": "info",
        },
        daemon=True,
    )
    dashboard_thread.start()
    dns_server.serve_forever()


if __name__ == "__main__":
    main()