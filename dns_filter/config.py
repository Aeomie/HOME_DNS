"""Load and validate DNS filter configuration from YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ListenConfig:
    host: str
    port: int


@dataclass(frozen=True)
class DNSConfig:
    listen: ListenConfig
    upstreams: list[str]
    timeout_seconds: float
    blocklist_path: str
    local_records_path: str


def load_config(path: str | Path = "config.yml") -> DNSConfig:
    """Load a DNS configuration file and validate its required values."""
    config_path = Path(path)
    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            raw_config = yaml.safe_load(config_file)
    except OSError as exc:
        raise ValueError(f"could not read configuration file {config_path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in configuration file {config_path}") from exc

    if not isinstance(raw_config, dict):
        raise ValueError("configuration root must be a mapping")

    listen = raw_config.get("listen")
    if not isinstance(listen, dict):
        raise ValueError("listen must be a mapping")

    host = listen.get("host")
    if not isinstance(host, str) or not host.strip():
        raise ValueError("listen.host must be a string")
    
    port = listen.get("port")
    if isinstance(port, bool) or not isinstance(port, int):
        raise ValueError("listen.port must be an integer")
    
    if not 1 <= port <= 65535:
        raise ValueError("listen.port must be between 1 and 65535")

    upstreams = raw_config.get("upstream")
    if (
        not isinstance(upstreams, list)
        or not upstreams
        or any(
            not isinstance(upstream, str) or not upstream.strip()
            for upstream in upstreams
        )
    ):
        raise ValueError("upstream must be a non-empty list")
    

    timeout_seconds = raw_config.get("timeout_seconds")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
    ):
        raise ValueError("timeout_seconds must be a number")
    
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    blocklist_path = raw_config.get("blocklist_path", "data/blocked.txt")
    local_records_path = raw_config.get(
        "local_records_path", "data/local_records.txt"
    )
    for name, value in (
        ("blocklist_path", blocklist_path),
        ("local_records_path", local_records_path),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")

    return DNSConfig(
        listen=ListenConfig(host=host.strip(), port=port),
        upstreams=upstreams,
        timeout_seconds=timeout_seconds,
        blocklist_path=blocklist_path.strip(),
        local_records_path=local_records_path.strip(),
    )


CONFIG = load_config()