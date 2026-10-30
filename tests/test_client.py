import struct

import pytest

from dns_filter.client import build_query, encode_domain


def test_encode_domain_uses_dns_label_lengths() -> None:
    assert encode_domain("Example.COM.") == b"\x07example\x03com\x00"


def test_build_query_contains_one_a_question() -> None:
    transaction_id, query = build_query("example.com")

    assert len(query) == 29
    assert struct.unpack("!H", query[:2])[0] == transaction_id
    assert struct.unpack("!HHHH", query[4:12]) == (1, 0, 0, 0)
    assert query[-4:] == b"\x00\x01\x00\x01"


@pytest.mark.parametrize("domain", ["", "example..com", "a" * 64])
def test_encode_domain_rejects_invalid_domains(domain: str) -> None:
    with pytest.raises(ValueError):
        encode_domain(domain)
