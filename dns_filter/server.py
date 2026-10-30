"""Synchronous UDP DNS request inspector for the first project milestone."""

from __future__ import annotations

import argparse
import logging
import socket

from .packet import DNSPacketError, parse_question, parse_header
from .resolver import DEFAULT_UPSTREAMS, UpstreamResolutionError, UpstreamResolver

LOGGER = logging.getLogger(__name__)


class UDPParser:
    """Receive DNS requests, parse them, and log their questions.

    This milestone intentionally does not send responses. The resolver and
    response path will be added after packet parsing is tested.
    """

    
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 1053,
        resolver: UpstreamResolver | None = None,
    ) -> None:
        """
        host : localhost by default
        port : By default it should be 53 but for testing purposes we will use 5353
        """
        self.address = (host, port)
        self.resolver = resolver or UpstreamResolver()

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
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1053)
    parser.add_argument(
        "--upstream",
        action="append",
        dest="upstreams",
        choices=None,
        help=(
            "upstream DNS IPv4 address; repeat to set order "
            f"(default: {', '.join(DEFAULT_UPSTREAMS)})"
        ),
    )
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    upstreams = tuple(args.upstreams) if args.upstreams else DEFAULT_UPSTREAMS
    resolver = UpstreamResolver(upstreams=upstreams, timeout=args.timeout)
    UDPParser(args.host, args.port, resolver).serve_forever()


if __name__ == "__main__":
    main()