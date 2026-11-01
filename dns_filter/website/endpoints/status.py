"""Dashboard status endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..auth import auth_for, is_loopback
from ..state import HISTORY_WINDOWS, DashboardState, PolicySnapshot

router = APIRouter()


def _can_view_clients(request: Request) -> bool:
    """Client IPs show which device visited what, so they need local or admin access."""
    return is_loopback(request) or auth_for(request).is_authenticated(request)


@router.get("/api/status")
def status(request: Request) -> dict[str, object]:
    state: DashboardState = request.app.state.dashboard_state
    policy_snapshot: PolicySnapshot = request.app.state.policy_snapshot
    snapshot = state.snapshot(policy_snapshot)
    if not _can_view_clients(request):
        snapshot["recent_blocked"] = [
            {**item, "client": None} for item in snapshot["recent_blocked"]
        ]
    return snapshot


@router.get("/api/blocked-history")
def blocked_history(request: Request, window: int = 3600) -> dict[str, object]:
    if window not in HISTORY_WINDOWS:
        raise HTTPException(status_code=400, detail="unsupported history window")
    state: DashboardState = request.app.state.dashboard_state
    history = state.history(window)
    if not _can_view_clients(request):
        history["devices"] = None
        history["bars"] = [
            {key: value for key, value in bar.items() if key != "clients"}
            for bar in history["bars"]
        ]
    return history
