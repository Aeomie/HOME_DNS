"""Admin login endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from ..auth import SESSION_COOKIE, auth_for, is_loopback

PAGES_DIR = Path(__file__).parent.parent / "pages"
router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str
    token: str


@router.get("/admin/login", include_in_schema=False)
def login_page() -> FileResponse:
    return FileResponse(PAGES_DIR / "login.html", media_type="text/html")


@router.post("/admin/challenge", include_in_schema=False)
def create_challenge(request: Request) -> dict[str, str]:
    auth_for(request).create_challenge()
    return {"status": "Token generated. Enter the token shown in the server console."}


@router.get("/admin/access", include_in_schema=False)
def admin_access(request: Request) -> dict[str, bool]:
    return {
        "can_view_docs": is_loopback(request)
        or auth_for(request).is_authenticated(request),
    }


@router.post("/admin/login", include_in_schema=False)
def login(
    request: Request,
    payload: LoginRequest,
) -> JSONResponse:
    session = auth_for(request).login(
        payload.username,
        payload.password,
        payload.token,
    )
    response = JSONResponse({"status": "ok"})
    response.set_cookie(
        SESSION_COOKIE,
        session,
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=8 * 60 * 60,
    )
    return response
