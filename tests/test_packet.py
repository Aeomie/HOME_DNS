import struct

import pytest

from dns_filter.packet import DNSPacketError, parse_header, parse_question


def make_query(domain: str, query_type: int = 1, query_class: int = 1) -> bytes:
    labels = b"".join(
        bytes([len(label)]) + label.encode("ascii")
        for label in domain.rstrip(".").split(".")
    )
    header = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
    return header + labels + b"\x00" + struct.pack("!HH", query_type, query_class)


def test_parse_header_returns_header_metadata() -> None:
    header = parse_header(make_query("Example.COM."))

    assert header.transaction_id == 0x1234
    assert header.flags == 0x0100
    assert header.question_count == 1
    assert header.answers == 0
    assert header.authority == 0
    assert header.additional == 0


def test_parse_question_returns_domain_and_metadata() -> None:
    data = make_query("Example.COM.")
    header = parse_header(data)
    question = parse_question(data, header)

    assert question.transaction_id == header.transaction_id
    assert question.domain == "example.com"
    assert question.query_type == 1
    assert question.query_class == 1


@pytest.mark.parametrize(
    "data, message",
    [
        (b"\x00" * 11, "header"),
        (struct.pack("!HHHHHH", 1, 0, 2, 0, 0, 0), "exactly one"),
    ],
)
def test_parse_header_rejects_malformed_requests(
    data: bytes, message: str
) -> None:
    with pytest.raises(DNSPacketError, match=message):
        parse_header(data)


def test_parse_question_rejects_truncated_domain() -> None:
    data = struct.pack("!HHHHHH", 1, 0, 1, 0, 0, 0) + b"\x03ab"
    header = parse_header(data)

    with pytest.raises(DNSPacketError, match="domain"):
        parse_question(data, header)
