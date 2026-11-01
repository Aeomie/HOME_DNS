from types import SimpleNamespace

from dns_filter.website.endpoints.status import blocked_history, status
from dns_filter.website.state import HISTORY_SECONDS, DashboardState

NOW = 1_000_000_000.0
HOUR = 60 * 60


def test_recent_blocked_records_client_and_type() -> None:
    state = DashboardState()
    state.record_blocked("ads.example.com", "192.168.1.7", 28, now=NOW)
    state.record_blocked("ads.example.com", "192.168.1.7", 999, now=NOW)

    assert state.blocked_queries == 2
    assert state.recent_blocked[0]["type"] == "999"
    assert state.recent_blocked[1]["client"] == "192.168.1.7"
    assert state.recent_blocked[1]["type"] == "AAAA"


def test_history_counts_queries_in_the_right_bars() -> None:
    state = DashboardState()
    state.record_blocked("a.example.com", "10.0.0.1", 1, now=NOW)
    state.record_blocked("a.example.com", "10.0.0.2", 1, now=NOW)
    state.record_blocked("b.example.com", "10.0.0.1", 1, now=NOW - 120)

    history = state.history(HOUR, now=NOW)

    assert len(history["bars"]) == 60
    assert history["total"] == 3
    assert history["bars"][-1]["count"] == 2
    assert history["bars"][-3]["count"] == 1
    assert history["top_domains"] == [
        {"domain": "a.example.com", "count": 2},
        {"domain": "b.example.com", "count": 1},
    ]


def test_history_excludes_queries_outside_the_window() -> None:
    state = DashboardState()
    state.record_blocked("old.example.com", "10.0.0.1", 1, now=NOW - 2 * HOUR)
    state.record_blocked("new.example.com", "10.0.0.1", 1, now=NOW)

    history = state.history(5 * 60, now=NOW)

    assert history["total"] == 1
    assert history["top_domains"] == [{"domain": "new.example.com", "count": 1}]
    assert state.history(6 * HOUR, now=NOW)["total"] == 2


def test_history_drops_buckets_older_than_a_day() -> None:
    state = DashboardState()
    state.record_blocked("old.example.com", "10.0.0.1", 1, now=NOW)
    state.record_blocked(
        "new.example.com", "10.0.0.1", 1, now=NOW + HISTORY_SECONDS + 60
    )

    assert len(state._history) == 1


def _viewer(host: str, state: DashboardState, authenticated: bool = False):
    auth = SimpleNamespace(is_authenticated=lambda request: authenticated)
    app_state = SimpleNamespace(
        dashboard_state=state,
        policy_snapshot=lambda: (set(), {}),
        admin_auth=auth,
    )
    return SimpleNamespace(
        app=SimpleNamespace(state=app_state),
        client=SimpleNamespace(host=host),
    )


def test_status_hides_client_ip_from_remote_viewers() -> None:
    state = DashboardState()
    state.record_blocked("ads.example.com", "192.168.1.7", 1, now=NOW)

    assert status(_viewer("127.0.0.1", state))["recent_blocked"][0]["client"]
    assert status(_viewer("203.0.113.9", state, True))["recent_blocked"][0]["client"]
    remote = status(_viewer("203.0.113.9", state))["recent_blocked"][0]
    assert remote["client"] is None
    assert remote["domain"] == "ads.example.com"


def test_history_breaks_down_devices_and_query_types() -> None:
    state = DashboardState()
    state.record_blocked("a.example.com", "10.0.0.1", 1, now=NOW)
    state.record_blocked("b.example.com", "10.0.0.1", 28, now=NOW)
    state.record_blocked("a.example.com", "10.0.0.2", 1, now=NOW)

    history = state.history(HOUR, now=NOW)

    assert history["bars"][-1]["clients"] == {"10.0.0.1": 2, "10.0.0.2": 1}
    assert history["devices"] == [
        {"client": "10.0.0.1", "count": 2},
        {"client": "10.0.0.2", "count": 1},
    ]
    assert history["types"] == [
        {"type": "A", "count": 2},
        {"type": "AAAA", "count": 1},
    ]


def test_history_hides_devices_from_remote_viewers() -> None:
    state = DashboardState()
    state.record_blocked("ads.example.com", "192.168.1.7", 1)

    local = blocked_history(_viewer("127.0.0.1", state), window=HOUR)
    remote = blocked_history(_viewer("203.0.113.9", state), window=HOUR)

    assert local["devices"][0]["client"] == "192.168.1.7"
    assert remote["devices"] is None
    assert remote["total"] == 1
    assert "clients" not in remote["bars"][-1]
