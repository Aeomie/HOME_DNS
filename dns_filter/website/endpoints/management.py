"""Endpoints for managing local DNS policy files."""

from __future__ import annotations

from ipaddress import IPv4Address
from math import ceil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from ...local_records import normalize_domain
from ...policy import (
    PolicyLists,
    append_to_custom_list,
    load_allowed_lists,
    load_blocked_lists,
    load_resolvers,
    save_resolvers,
    set_allowed_active,
    set_blocked_active,
)
from ...config import CONFIG
from ..auth import require_admin

router = APIRouter(prefix="/api")


class BlockedDomainRequest(BaseModel):
    domain: str


class LocalRecordRequest(BaseModel):
    domain: str
    address: IPv4Address


class BulkDomainsRequest(BaseModel):
    domains: list[str]


class BulkLocalRecordsRequest(BaseModel):
    records: list[str]


class ToggleRequest(BaseModel):
    active: bool


class ResolverRequest(BaseModel):
    address: str


def _domain(value: str) -> str:
    domain = normalize_domain(value.strip())
    if not domain or " " in domain or "/" in domain:
        raise HTTPException(status_code=400, detail="invalid domain")
    return domain


def _page(
    lists: PolicyLists,
    directory: Path,
    page: int,
    size: int,
    search: str,
) -> dict[str, object]:
    term = search.strip().lower()
    rows = [row for row in lists.rows if term in row[0]] if term else lists.rows
    pages = max(1, ceil(len(rows) / size))
    page = min(page, pages)
    return {
        "entries": [
            {"domain": domain, "address": value, "active": active}
            for domain, value, active in rows[(page - 1) * size : page * size]
        ],
        "matched": len(rows),
        "total": len(lists.entries),
        "active": lists.active,
        "page": page,
        "pages": pages,
        "size": size,
        "directory": str(directory),
        "files": [
            {"name": file.name, "entries": file.entries, "skipped": file.skipped}
            for file in lists.files
        ],
    }


@router.get("/blocked")
def blocked_domains(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str = "",
) -> dict[str, object]:
    directory: Path = request.app.state.blocked_lists_dir
    return _page(load_blocked_lists(directory), directory, page, size, search)


@router.post("/blocked")
def add_blocked_domain(
    payload: BlockedDomainRequest, request: Request
) -> dict[str, str]:
    require_admin(request)
    domain = _domain(payload.domain)
    directory: Path = request.app.state.blocked_lists_dir
    if domain in load_blocked_lists(directory).entries:
        raise HTTPException(status_code=409, detail="domain is already blocked")
    append_to_custom_list(directory, [domain])
    return {"domain": domain, "status": "blocked"}


@router.post("/blocked/bulk")
def add_blocked_domains(
    payload: BulkDomainsRequest, request: Request
) -> dict[str, int]:
    require_admin(request)
    directory: Path = request.app.state.blocked_lists_dir
    entries = load_blocked_lists(directory).entries
    added = dict.fromkeys(
        domain
        for domain in map(_domain, payload.domains)
        if domain not in entries
    )
    if added:
        append_to_custom_list(directory, list(added))
    return {"added": len(added), "total": len(entries) + len(added)}


@router.patch("/blocked/{domain:path}")
def toggle_blocked_domain(
    domain: str, payload: ToggleRequest, request: Request
) -> dict[str, object]:
    require_admin(request)
    normalized = _domain(domain)
    directory: Path = request.app.state.blocked_lists_dir
    if normalized not in load_blocked_lists(directory).entries:
        raise HTTPException(status_code=404, detail="domain not found")
    set_blocked_active(directory, normalized, payload.active)
    return {"domain": normalized, "active": payload.active}


@router.get("/local-records")
def local_records(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str = "",
) -> dict[str, object]:
    directory: Path = request.app.state.allowed_lists_dir
    return _page(load_allowed_lists(directory), directory, page, size, search)


@router.post("/local-records")
def add_local_record(
    payload: LocalRecordRequest, request: Request
) -> dict[str, str]:
    require_admin(request)
    domain = _domain(payload.domain)
    directory: Path = request.app.state.allowed_lists_dir
    if domain in load_allowed_lists(directory).entries:
        raise HTTPException(status_code=409, detail="local record already exists")
    address = str(payload.address)
    append_to_custom_list(directory, [f"{address} {domain}"])
    return {"domain": domain, "address": address, "status": "created"}


@router.post("/local-records/bulk")
def add_local_records(
    payload: BulkLocalRecordsRequest, request: Request
) -> dict[str, int]:
    require_admin(request)
    directory: Path = request.app.state.allowed_lists_dir
    entries = load_allowed_lists(directory).entries
    added: dict[str, str] = {}
    for raw_record in payload.records:
        fields = raw_record.strip().split()
        if len(fields) != 2:
            raise HTTPException(
                status_code=400,
                detail="each local record must be '<IPv4 address> <domain>'",
            )
        try:
            address = str(IPv4Address(fields[0]))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid IPv4 address") from exc
        domain = _domain(fields[1])
        if domain not in entries:
            added.setdefault(domain, address)
    if added:
        append_to_custom_list(
            directory, [f"{address} {domain}" for domain, address in added.items()]
        )
    return {"added": len(added), "total": len(entries) + len(added)}


@router.patch("/local-records/{domain:path}")
def toggle_local_record(
    domain: str, payload: ToggleRequest, request: Request
) -> dict[str, object]:
    require_admin(request)
    normalized = _domain(domain)
    directory: Path = request.app.state.allowed_lists_dir
    if normalized not in load_allowed_lists(directory).entries:
        raise HTTPException(status_code=404, detail="local record not found")
    set_allowed_active(directory, normalized, payload.active)
    return {"domain": normalized, "active": payload.active}


@router.get("/resolvers")
def resolvers() -> list[dict[str, object]]:
    entries = load_resolvers(CONFIG.resolvers_path, CONFIG.upstreams)
    return [
        {"address": address, "active": active}
        for address, active in sorted(entries.items())
    ]


@router.post("/resolvers")
def add_resolver(payload: ResolverRequest, request: Request) -> dict[str, object]:
    require_admin(request)
    try:
        address = str(IPv4Address(payload.address.strip()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid resolver address") from exc
    entries = load_resolvers(CONFIG.resolvers_path, CONFIG.upstreams)
    if address in entries:
        raise HTTPException(status_code=409, detail="resolver already exists")
    entries[address] = True
    save_resolvers(CONFIG.resolvers_path, entries)
    return {"address": address, "active": True}


@router.patch("/resolvers/{address}")
def toggle_resolver(
    address: str, payload: ToggleRequest, request: Request
) -> dict[str, object]:
    require_admin(request)
    try:
        normalized = str(IPv4Address(address))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid resolver address") from exc
    entries = load_resolvers(CONFIG.resolvers_path, CONFIG.upstreams)
    if normalized not in entries:
        raise HTTPException(status_code=404, detail="resolver not found")
    entries[normalized] = payload.active
    save_resolvers(CONFIG.resolvers_path, entries)
    return {"address": normalized, "active": payload.active}
