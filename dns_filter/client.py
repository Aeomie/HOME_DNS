"""Small UDP client for sending DNS questions to the local server."""

from __future__ import annotations

import argparse
import ipaddress
import secrets
import socket
import struct

from .enums import QCLASS, QTYPE
from .config import CONFIG


def read_name(data: bytes, offset: int) -> tuple[str, int]:
    """Read a DNS name and return it with the next sequential offset."""
    labels: list[str] = []
    current_offset = offset
    next_offset: int | None = None
    visited_offsets: set[int] = set()

    while True:
        if current_offset >= len(data):
            raise ValueError("DNS name is truncated")
        if current_offset in visited_offsets:
            raise ValueError("DNS name compression loop detected")
        visited_offsets.add(current_offset)

        length = data[current_offset]
        if length == 0:
            current_offset += 1
            if next_offset is None:
                next_offset = current_offset
            return ".".join(labels), next_offset

        if length & 0xC0 == 0xC0:
            if current_offset + 1 >= len(data):
                raise ValueError("DNS compression pointer is truncated")
            pointer = ((length & 0x3F) << 8) | data[current_offset + 1]
            if pointer >= len(data):
                raise ValueError("DNS compression pointer is out of bounds")
            if next_offset is None:
                next_offset = current_offset + 2
            current_offset = pointer
            continue

        if length > 63:
            raise ValueError("invalid DNS label length")
        label_start = current_offset + 1
        label_end = label_start + length
        if label_end > len(data):
            raise ValueError("DNS label is truncated")
        try:
            labels.append(data[label_start:label_end].decode("ascii"))
        except UnicodeDecodeError as exc:
            raise ValueError("DNS label is not valid ASCII") from exc
        current_offset = label_end


def answer_offset(response: bytes) -> int:
    """Return the offset immediately after the response question."""
    if len(response) < 12:
        raise ValueError("DNS response header is truncated")
    question_count = struct.unpack("!H", response[4:6])[0]
    offset = 12
    for _ in range(question_count):
        _, offset = read_name(response, offset)
        if offset + 4 > len(response):
            raise ValueError("DNS response question is truncated")
        offset += 4
    return offset


def format_answers(response: bytes) -> list[str]:
    """Format answer records, including IPv4 and IPv6 address records."""
    if len(response) < 12:
        raise ValueError("DNS response header is truncated")

    answer_count = struct.unpack("!H", response[6:8])[0]
    offset = answer_offset(response)
    answers: list[str] = []

    for _ in range(answer_count):
        name, offset = read_name(response, offset)
        if offset + 10 > len(response):
            raise ValueError("DNS answer header is truncated")

        record_type, record_class, ttl, data_length = struct.unpack(
            "!HHIH", response[offset : offset + 10]
        )
        offset += 10
        data_end = offset + data_length
        if data_end > len(response):
            raise ValueError("DNS answer data is truncated")

        record_data = response[offset:data_end]
        if record_type == QTYPE.A and data_length == 4:
            value = str(ipaddress.ip_address(record_data))
            answers.append(f"{name} A {value} TTL={ttl}")
        elif record_type == QTYPE.AAAA and data_length == 16:
            value = str(ipaddress.ip_address(record_data))
            answers.append(f"{name} AAAA {value} TTL={ttl}")
        elif record_type == QTYPE.CNAME:
            cname, _ = read_name(response, offset)
            answers.append(f"{name} CNAME {cname} TTL={ttl}")
        else:
            answers.append(
                f"{name} TYPE={record_type} CLASS={record_class} "
                f"RDLENGTH={data_length} TTL={ttl}"
            )
        offset = data_end

    return answers


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
        print(f"response transaction ID {struct.unpack('!H', response[:2])[0]}")
        print(f"response header flags {struct.unpack('!H', response[2:4])[0]:#06x}")
        print(f"response question count {struct.unpack('!H', response[4:6])[0]}")
        answer_count = struct.unpack("!H", response[6:8])[0]
        print(f"response answer count {answer_count}")
        for answer in format_answers(response):
            print(f"answer {answer}")



def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain", nargs="?", default="example.com")
    parser.add_argument("--host", default=CONFIG.listen.host)
    parser.add_argument("--port", type=int, default=CONFIG.listen.port)
    parser.add_argument(
        "--wait",
        action="store_true",
        help="wait for a response after sending the query",
    )
    args = parser.parse_args()

    send_query(args.domain, args.host, args.port, args.wait)


if __name__ == "__main__":
    main()
