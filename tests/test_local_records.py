import pytest

from dns_filter.local_records import load_local_records, normalize_domain


def test_local_records_normalize_domains_and_addresses() -> None:
    assert load_local_records({"MyMoney5423.": "192.168.1.50"}) == {
        "mymoney5423": "192.168.1.50"
    }


def test_local_records_reject_invalid_addresses() -> None:
    with pytest.raises(ValueError, match="IPv4"):
        load_local_records({"mymoney5423": "not-an-ip"})


def test_normalize_domain_removes_trailing_dot() -> None:
    assert normalize_domain("MyMoney5423.") == "mymoney5423"
