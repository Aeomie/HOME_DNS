"""Local exact-domain blocklist support."""

from __future__ import annotations

from pathlib import Path


def normalize_domain(domain: str) -> str:
    """Normalize a domain for consistent blocklist comparisons."""
    return domain.rstrip(".").lower()


def load_blocklist(path: str | Path) -> set[str]:
    """Load one exact domain per line, ignoring blanks and comments."""
    blocklist_path = Path(path)
    try:
        lines = blocklist_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"could not read blocklist file {blocklist_path}") from exc

    domains: set[str] = set()
    for line in lines:
        domain = line.split("#", 1)[0].strip()
        if domain:
            domains.add(normalize_domain(domain))
    return domains
