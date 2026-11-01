"""Loopback-only Swagger documentation routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from .auth import auth_for, is_loopback

router = APIRouter(prefix="/internal")


def _require_loopback(request: Request) -> None:
    if not is_loopback(request) and not auth_for(request).is_authenticated(request):
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/swagger", include_in_schema=False)
def swagger_ui(request: Request):
    _require_loopback(request)
    swagger_page = get_swagger_ui_html(
        openapi_url="/internal/openapi.json",
        title="DNS Filter Internal API",
    )
    return swagger_page


@router.get("/openapi.json", include_in_schema=False)
def openapi_schema(request: Request) -> JSONResponse:
    _require_loopback(request)
    app = request.app
    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    return JSONResponse(schema)
