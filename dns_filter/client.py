"""Small UDP client for sending DNS questions to the local server."""

from __future__ import annotations

import argparse
import secrets
import socket
import struct

from .enums import QCLASS, QTYPE


def encode_domain(domain: str) -> bytes:
    """Encode a dotted domain name as DNS length-prefixed labels."""
    normalized = domain.rstrip(".").lower()
    if not normalized:
        raise ValueError("domain must not be empty")

    encoded_labels = []
    for label in normalized.split("."):
        label_bytes = label.encode("ascii")
        if not label_bytes:
            raise ValueError("domain contains an empty label")
        if len(label_bytes) > 63:
            raise ValueError("a DNS label cannot exceed 63 bytes")
        encoded_labels.append(bytes([len(label_bytes)]) + label_bytes)

    encoded = b"".join(encoded_labels) + b"\x00"
    if len(encoded) > 255:
        raise ValueError("encoded domain name cannot exceed 255 bytes")
    return encoded


def build_query(
    domain: str,
    query_type: QTYPE = QTYPE.A,
    query_class: QCLASS = QCLASS.IN,
) -> tuple[int, bytes]:
    """Build one DNS query and return its transaction ID and wire bytes."""
    transaction_id = secrets.randbelow(0x10000)
    header = struct.pack(
        "!HHHHHH",
        transaction_id,
        0x0100,
        1,
        0,
        0,
        0,
    )
    question = encode_domain(domain) + struct.pack(
        "!HH",
        int(query_type),
        int(query_class),
    )
    return transaction_id, header + question


def send_query(
    domain: str,
    host: str = "127.0.0.1",
    port: int = 1053,
    wait_for_response: bool = False,
    timeout: float = 2.0,
) -> None:
    """Send one query and optionally wait for a response."""
    transaction_id, request = build_query(domain)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
        client_socket.sendto(request, (host, port))
        print(
            f"sent {len(request)} bytes for {domain.rstrip('.').lower()} "
            f"to {host}:{port} (transaction ID {transaction_id})"
        )

        if not wait_for_response:
            return

        client_socket.settimeout(timeout)
        try:
            response, server_address = client_socket.recvfrom(4096)
        except socket.timeout:
            print(f"no response received within {timeout:g} seconds")
            return

        print(f"received {len(response)} bytes from {server_address[0]}:{server_address[1]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain", nargs="?", default="example.com")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1053)
    parser.add_argument(
        "--wait",
        action="store_true",
        help="wait for a response after sending the query",
    )
    args = parser.parse_args()

    send_query(args.domain, args.host, args.port, args.wait)


if __name__ == "__main__":
    main()
