"""Single-admin authentication for the dashboard."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from ..admin import ADMIN_CREDENTIALS_PATH, HASH_ITERATIONS

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

CHALLENGE_TTL_SECONDS = 120
SESSION_TTL_SECONDS = 8 * 60 * 60
SESSION_COOKIE = "dns_filter_admin"


def _configured_credentials() -> tuple[str, str, str | None] | None:
    environment_username = os.environ.get("DNS_FILTER_ADMIN_USERNAME")
    environment_password = os.environ.get("DNS_FILTER_ADMIN_PASSWORD")
    if environment_username and environment_password:
        return environment_username, environment_password, None

    try:
        credentials: dict[str, Any] = json.loads(
            ADMIN_CREDENTIALS_PATH.read_text(encoding="utf-8")
        )
        username = credentials["username"]
        salt = bytes.fromhex(credentials["salt"])
        password_hash = credentials["password_hash"]
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None

    if (
        not isinstance(username, str)
        or not isinstance(password_hash, str)
        or not salt
    ):
        return None
    return username, password_hash, salt.hex()


@dataclass
class AdminAuth:
    """In-memory one-admin challenge and session store."""

    challenges: dict[str, float] = field(default_factory=dict)
    sessions: dict[str, float] = field(default_factory=dict)

    def create_challenge(self) -> str:
        self._purge()
        token = secrets.token_urlsafe(24)
        self.challenges[token] = time.time() + CHALLENGE_TTL_SECONDS
        logger.warning("Admin login token (expires in 2 minutes): %s", token)
        return token

    def login(self, username: str, password: str, token: str) -> str:
        configured = _configured_credentials()
        if configured is None:
            raise HTTPException(
                status_code=503,
                detail="Admin credentials are not configured on the server",
            )
        configured_username, configured_password, salt_hex = configured

        self._purge()
        if salt_hex is None:
            password_matches = hmac.compare_digest(password, configured_password)
        else:
            password_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                HASH_ITERATIONS,
            ).hex()
            password_matches = hmac.compare_digest(
                password_hash,
                configured_password,
            )
        valid_credentials = hmac.compare_digest(
            username,
            configured_username,
        ) and password_matches
        challenge_expiry = self.challenges.pop(token, None)
        if not valid_credentials or challenge_expiry is None:
            raise HTTPException(status_code=401, detail="Invalid admin credentials or token")

        session = secrets.token_urlsafe(32)
        self.sessions[session] = time.time() + SESSION_TTL_SECONDS
        return session

    def is_authenticated(self, request: Request) -> bool:
        self._purge()
        session = request.cookies.get(SESSION_COOKIE)
        return bool(session and session in self.sessions)

    def require_admin(self, request: Request) -> None:
        if not self.is_authenticated(request):
            raise HTTPException(status_code=401, detail="Admin login required")

    def _purge(self) -> None:
        now = time.time()
        self.challenges = {
            token: expiry for token, expiry in self.challenges.items() if expiry > now
        }
        self.sessions = {
            session: expiry for session, expiry in self.sessions.items() if expiry > now
        }


def auth_for(request: Request) -> AdminAuth:
    return request.app.state.admin_auth


def is_loopback(request: Request) -> bool:
    client = request.client
    if client is None:
        return False
    try:
        return ipaddress.ip_address(client.host).is_loopback
    except ValueError:
        return client.host.lower() == "localhost"


def require_admin(request: Request) -> None:
    auth_for(request).require_admin(request)
