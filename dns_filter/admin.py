"""Create the single administrator account used by the dashboard."""

from __future__ import annotations

import getpass
import hashlib
import json
import secrets
from pathlib import Path

ADMIN_CREDENTIALS_PATH = Path("data/admin_credentials.json")
HASH_ITERATIONS = 600_000


def password_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        HASH_ITERATIONS,
    ).hex()


def create_admin() -> None:
    """Prompt for credentials and save a salted password hash."""
    username = input("Admin username: ").strip()
    if not username:
        raise SystemExit("Admin username cannot be empty.")

    password = getpass.getpass("Admin password: ")
    confirmation = getpass.getpass("Confirm admin password: ")
    if not password:
        raise SystemExit("Admin password cannot be empty.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    salt = secrets.token_bytes(16)
    credentials = {
        "username": username,
        "salt": salt.hex(),
        "password_hash": password_hash(password, salt),
    }
    ADMIN_CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ADMIN_CREDENTIALS_PATH.write_text(
        json.dumps(credentials, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Admin credentials saved to {ADMIN_CREDENTIALS_PATH}.")


if __name__ == "__main__":
    create_admin()
