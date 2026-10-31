"""Local DNS records loaded from configuration."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Mapping


def normalize_domain(domain: str) -> str:
    """Normalize domain names for local-record lookups."""
    return domain.rstrip(".").lower()


def load_local_records(raw_records: object) -> dict[str, str]:
    """Validate and normalize configured domain-to-IPv4 records."""
    if raw_records is None:
        return {}
    if not isinstance(raw_records, Mapping):
        raise ValueError("local_records must be a mapping of domains to IPv4 addresses")

    records: dict[str, str] = {}
    for raw_domain, raw_address in raw_records.items():
        if not isinstance(raw_domain, str) or not raw_domain.strip():
            raise ValueError("local record domains must be non-empty strings")
        if not isinstance(raw_address, str):
            raise ValueError(f"local record for {raw_domain!r} must be an IPv4 address")

        domain = normalize_domain(raw_domain.strip())
        try:
            address = str(ipaddress.IPv4Address(raw_address.strip()))
        except ipaddress.AddressValueError as exc:
            raise ValueError(
                f"local record for {raw_domain!r} must be an IPv4 address"
            ) from exc
        records[domain] = address
    return records


def load_local_records_file(path: str | Path) -> dict[str, str]:
    """Load hosts-style records: IPv4 address followed by domain."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"could not read local records file {path}") from exc

    raw_records: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        content = line.split("#", 1)[0].strip()
        if not content:
            continue
        fields = content.split()
        if len(fields) != 2:
            raise ValueError(
                f"local records file {path}, line {line_number}: "
                "expected '<IPv4 address> <domain>'"
            )
        address, domain = fields
        if domain in raw_records:
            raise ValueError(
                f"local records file {path}, line {line_number}: duplicate domain"
            )
        raw_records[domain] = address
    return load_local_records(raw_records)
