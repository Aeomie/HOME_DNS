"""Read and write the folders of blocked and allowed domain lists."""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Callable

from .local_records import normalize_domain

CUSTOM_LIST = "custom.txt"
DISABLED_PREFIX = "# disabled:"
HOSTS_SINKS = {"0.0.0.0", "127.0.0.1", "::", "::1"}
HOSTS_NAMES = {"localhost", "localhost.localdomain", "local", "broadcasthost"}
DOMAIN_PATTERN = re.compile(r"[a-z0-9_-]+(\.[a-z0-9_-]+)*")

Parsed = tuple[str, str | None] | None
Signature = tuple[tuple[str, int, int], ...]


@dataclass(frozen=True)
class ListFile:
    name: str
    entries: int
    skipped: int


@dataclass(frozen=True)
class PolicyLists:
    """Merged list files; shared through a cache, so treat it as read-only."""

    entries: dict[str, tuple[str | None, bool]]
    rows: list[tuple[str, str | None, bool]]
    active: int
    files: list[ListFile]


_cache: dict[Path, tuple[Signature, PolicyLists]] = {}
_cache_lock = Lock()


def list_files(directory: str | Path) -> list[Path]:
    folder = Path(directory)
    if not folder.is_dir():
        return []
    return sorted(path for path in folder.glob("*.txt") if path.is_file())


def list_signature(directory: str | Path) -> Signature:
    """Identify the current contents of a folder without reading its files."""
    signature = []
    for path in list_files(directory):
        stat = path.stat()
        signature.append((path.name, stat.st_mtime_ns, stat.st_size))
    return tuple(signature)


def _split_line(raw_line: str) -> tuple[str, bool] | None:
    line = raw_line.strip()
    active = True
    if line.startswith(DISABLED_PREFIX):
        line = line.removeprefix(DISABLED_PREFIX).strip()
        active = False
    elif not line or line.startswith(("#", "!")):
        return None
    content = line.split("#", 1)[0].strip()
    return (content, active) if content else None


def parse_blocked_line(content: str) -> Parsed:
    """Accept plain domains, hosts-file lines, and adblock-style ||domain^ rules."""
    if content.startswith("||"):
        content = content[2:].split("^", 1)[0]
    fields = content.split()
    if len(fields) == 2 and fields[0] in HOSTS_SINKS:
        if fields[1].lower() in HOSTS_NAMES:
            return None
        fields = fields[1:]
    if len(fields) != 1:
        return None
    domain = normalize_domain(fields[0])
    if not DOMAIN_PATTERN.fullmatch(domain):
        return None
    return (domain, None)


def parse_allowed_line(content: str) -> Parsed:
    fields = content.split()
    if len(fields) != 2:
        return None
    try:
        address = str(ipaddress.IPv4Address(fields[0]))
    except ipaddress.AddressValueError:
        return None
    domain = normalize_domain(fields[1])
    if not DOMAIN_PATTERN.fullmatch(domain):
        return None
    return (domain, address)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _load(
    directory: str | Path,
    parse: Callable[[str], Parsed],
) -> PolicyLists:
    folder = Path(directory)
    with _cache_lock:
        signature = list_signature(folder)
        cached = _cache.get(folder)
        if cached is not None and cached[0] == signature:
            return cached[1]

        entries: dict[str, tuple[str | None, bool]] = {}
        files: list[ListFile] = []
        for path in list_files(folder):
            count = 0
            skipped = 0
            for raw_line in _read(path).splitlines():
                split = _split_line(raw_line)
                if split is None:
                    continue
                content, active = split
                parsed = parse(content)
                if parsed is None:
                    skipped += 1
                    continue
                count += 1
                domain, value = parsed
                current = entries.get(domain)
                if current is None or (active and not current[1]):
                    entries[domain] = (value, active)
            files.append(ListFile(path.name, count, skipped))

        rows = sorted(
            (domain, value, active) for domain, (value, active) in entries.items()
        )
        lists = PolicyLists(
            entries=entries,
            rows=rows,
            active=sum(1 for _, _, active in rows if active),
            files=files,
        )
        _cache[folder] = (signature, lists)
        return lists


def load_blocked_lists(directory: str | Path) -> PolicyLists:
    return _load(directory, parse_blocked_line)


def load_allowed_lists(directory: str | Path) -> PolicyLists:
    return _load(directory, parse_allowed_line)


def load_blocklist(directory: str | Path) -> set[str]:
    """Return every actively blocked domain from a folder of list files."""
    return {
        domain
        for domain, _, active in load_blocked_lists(directory).rows
        if active
    }


def load_allowed_records(directory: str | Path) -> dict[str, str]:
    """Return active domain-to-IPv4 records from a folder of list files."""
    return {
        domain: value
        for domain, value, active in load_allowed_lists(directory).rows
        if active and value is not None
    }


def _set_active(
    directory: str | Path,
    domain: str,
    active: bool,
    parse: Callable[[str], Parsed],
) -> None:
    """Rewrite only the lines for one domain, in every file that lists it."""
    for path in list_files(directory):
        text = _read(path)
        if domain not in text.lower():
            continue
        lines = text.splitlines()
        changed = False
        for index, raw_line in enumerate(lines):
            split = _split_line(raw_line)
            if split is None:
                continue
            parsed = parse(split[0])
            if parsed is None or parsed[0] != domain:
                continue
            lines[index] = split[0] if active else f"{DISABLED_PREFIX} {split[0]}"
            changed = True
        if changed:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def set_blocked_active(directory: str | Path, domain: str, active: bool) -> None:
    _set_active(directory, domain, active, parse_blocked_line)


def set_allowed_active(directory: str | Path, domain: str, active: bool) -> None:
    _set_active(directory, domain, active, parse_allowed_line)


def append_to_custom_list(directory: str | Path, lines: list[str]) -> None:
    """Add dashboard entries to custom.txt, leaving downloaded lists untouched."""
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / CUSTOM_LIST
    existing = _read(path) if path.exists() else ""
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    with path.open("a", encoding="utf-8") as custom_list:
        custom_list.write(prefix + "".join(f"{line}\n" for line in lines))


def load_resolvers(path: str | Path, defaults: list[str]) -> dict[str, bool]:
    resolver_path = Path(path)
    if not resolver_path.exists():
        return {resolver: True for resolver in defaults}
    data = json.loads(resolver_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("resolver configuration must be a mapping")
    return {
        str(address): bool(active)
        for address, active in data.items()
        if isinstance(address, str)
    }


def save_resolvers(path: str | Path, entries: dict[str, bool]) -> None:
    Path(path).write_text(
        json.dumps(dict(sorted(entries.items())), indent=2) + "\n",
        encoding="utf-8",
    )
