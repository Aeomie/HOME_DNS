"""Synchronous UDP DNS request inspector for the first project milestone."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from .config import CONFIG
import socket

from .blocklist import load_blocklist
from .packet import (
    DNSPacketError,
    build_a_response,
    build_nxdomain_response,
    parse_header,
    parse_question,
)
from .resolver import UpstreamResolutionError, UpstreamResolver
from .local_records import load_local_records_file

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
        blocklist_path: str | Path | None = None,
        local_records_path: str | Path | None = None,
    ) -> None:
        """
        host : localhost by default
        port : By default it should be 53 but for testing purposes we will use 5353
        """
        self.address = (host, port)
        self.resolver = resolver or UpstreamResolver()
        self.local_records = local_records or {}
        self.blocked_domains = blocked_domains or set()
        self.blocklist_path = Path(blocklist_path) if blocklist_path else None
        self.local_records_path = (
            Path(local_records_path) if local_records_path else None
        )
        self._policy_mtimes: dict[Path, int] = {}
        self._remember_policy_mtimes()

    def _remember_policy_mtimes(self) -> None:
        for path in (self.blocklist_path, self.local_records_path):
            if path is not None:
                self._policy_mtimes[path] = path.stat().st_mtime_ns

    def _refresh_policy_files(self) -> None:
        """Reload changed policy files while keeping the server running."""
        if self.blocklist_path is not None:
            blocklist_mtime = self.blocklist_path.stat().st_mtime_ns
            if self._policy_mtimes.get(self.blocklist_path) != blocklist_mtime:
                self.blocked_domains = load_blocklist(self.blocklist_path)
                self._policy_mtimes[self.blocklist_path] = blocklist_mtime
                LOGGER.info("reloaded blocklist from %s", self.blocklist_path)

        if self.local_records_path is not None:
            records_mtime = self.local_records_path.stat().st_mtime_ns
            if self._policy_mtimes.get(self.local_records_path) != records_mtime:
                self.local_records = load_local_records_file(self.local_records_path)
                self._policy_mtimes[self.local_records_path] = records_mtime
                LOGGER.info("reloaded local records from %s", self.local_records_path)

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
    )
    blocked_domains = load_blocklist(CONFIG.blocklist_path)
    local_records = load_local_records_file(CONFIG.local_records_path)
    UDPParser(
        args.host,
        args.port,
        resolver,
        local_records,
        blocked_domains,
        CONFIG.blocklist_path,
        CONFIG.local_records_path,
    ).serve_forever()


if __name__ == "__main__":
    main()