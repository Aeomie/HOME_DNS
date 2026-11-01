"""FastAPI dashboard entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse

from ..config import CONFIG
from ..policy import load_allowed_records, load_blocklist
from .endpoints.management import router as management_router
from .endpoints.status import router as status_router
from .endpoints.admin import router as admin_router
from .auth import AdminAuth
from .state import DashboardState
from .swagger import router as swagger_router

PAGES_DIR = Path(__file__).with_name("pages")
PolicySnapshot = Callable[[], tuple[set[str], dict[str, str]]]


def create_app(
    policy_snapshot: PolicySnapshot | None = None,
    state: DashboardState | None = None,
) -> FastAPI:
    """Create the dashboard application and register its endpoint routers."""
    if policy_snapshot is None:

        def policy_snapshot() -> tuple[set[str], dict[str, str]]:
            return (
                load_blocklist(CONFIG.blocked_lists_dir),
                load_allowed_records(CONFIG.allowed_lists_dir),
            )

    app = FastAPI(
        title="DNS Filter Dashboard",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.dashboard_state = state or DashboardState()
    app.state.admin_auth = AdminAuth()
    app.state.policy_snapshot = policy_snapshot
    app.state.blocked_lists_dir = Path(CONFIG.blocked_lists_dir)
    app.state.allowed_lists_dir = Path(CONFIG.allowed_lists_dir)
    app.include_router(status_router)
    app.include_router(management_router)
    app.include_router(admin_router)
    app.include_router(swagger_router)

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(PAGES_DIR / "dashboard.html", media_type="text/html")

    @app.get("/manage", include_in_schema=False)
    def manage() -> RedirectResponse:
        return RedirectResponse("/manage/resolvers")

    @app.get("/manage/resolvers", include_in_schema=False)
    @app.get("/manage/blocked", include_in_schema=False)
    @app.get("/manage/allowed", include_in_schema=False)
    def manage_section() -> FileResponse:
        return FileResponse(PAGES_DIR / "manage.html", media_type="text/html")

    @app.get("/styles.css", include_in_schema=False)
    def styles() -> FileResponse:
        return FileResponse(PAGES_DIR / "styles.css", media_type="text/css")

    return app


app = create_app()


def main() -> None:
    """Run the standalone dashboard server."""
    uvicorn.run(
        app,
        host=CONFIG.dashboard.host,
        port=CONFIG.dashboard.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
