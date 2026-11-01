"""Thread-safe dashboard metrics."""

from __future__ import annotations

import time
from collections import Counter
from datetime import datetime, timezone
from threading import Lock
from typing import Callable

from ..enums import QueryType


PolicySnapshot = Callable[[], tuple[set[str], dict[str, str]]]

RECENT_LIMIT = 20
TOP_DOMAIN_LIMIT = 10
BUCKET_SECONDS = 10
# Chart window in seconds -> width of one bar in seconds.
HISTORY_WINDOWS = {
    5 * 60: 10,
    15 * 60: 30,
    60 * 60: 60,
    6 * 60 * 60: 10 * 60,
    24 * 60 * 60: 30 * 60,
}
HISTORY_SECONDS = max(HISTORY_WINDOWS) + max(HISTORY_WINDOWS.values())


def query_type_name(query_type: int) -> str:
    try:
        return QueryType(query_type).name
    except ValueError:
        return str(query_type)


class DashboardState:
    """Metrics collected by the DNS server for the dashboard."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.blocked_queries = 0
        self.recent_blocked: list[dict[str, str]] = []
        self._history: dict[int, Counter[tuple[str, str, str]]] = {}

    def record_blocked(
        self,
        domain: str,
        client: str,
        query_type: int,
        now: float | None = None,
    ) -> None:
        now = time.time() if now is None else now
        with self._lock:
            self.blocked_queries += 1
            type_name = query_type_name(query_type)
            self.recent_blocked.insert(
                0,
                {
                    "domain": domain,
                    "client": client,
                    "type": type_name,
                    "time": datetime.fromtimestamp(now, timezone.utc).isoformat(
                        timespec="seconds"
                    ),
                },
            )
            del self.recent_blocked[RECENT_LIMIT:]

            bucket = int(now) - int(now) % BUCKET_SECONDS
            self._history.setdefault(bucket, Counter())[
                (domain, client, type_name)
            ] += 1
            oldest = bucket - HISTORY_SECONDS
            if min(self._history) < oldest:
                self._history = {
                    start: domains
                    for start, domains in self._history.items()
                    if start >= oldest
                }

    def history(
        self, window: int, now: float | None = None
    ) -> dict[str, object]:
        """Return blocked query counts per bar, ending at the current bar."""
        now = time.time() if now is None else now
        width = HISTORY_WINDOWS[window]
        current = int(now) - int(now) % width
        starts = [
            current - width * index for index in range(window // width - 1, -1, -1)
        ]
        bars: dict[int, Counter[str]] = {start: Counter() for start in starts}
        domains: Counter[str] = Counter()
        clients: Counter[str] = Counter()
        types: Counter[str] = Counter()
        with self._lock:
            for start, bucket in self._history.items():
                bar = bars.get(start - start % width)
                if bar is None:
                    continue
                for (domain, client, type_name), count in bucket.items():
                    bar[client] += count
                    domains[domain] += count
                    clients[client] += count
                    types[type_name] += count
        return {
            "window": window,
            "bar_seconds": width,
            "total": clients.total(),
            "bars": [
                {
                    "start": start,
                    "count": bars[start].total(),
                    "clients": dict(bars[start]),
                }
                for start in starts
            ],
            "top_domains": [
                {"domain": domain, "count": count}
                for domain, count in domains.most_common(TOP_DOMAIN_LIMIT)
            ],
            "devices": [
                {"client": client, "count": count}
                for client, count in clients.most_common()
            ],
            "types": [
                {"type": type_name, "count": count}
                for type_name, count in types.most_common()
            ],
        }

    def snapshot(self, policy_snapshot: PolicySnapshot) -> dict[str, object]:
        blocked_domains, local_records = policy_snapshot()
        with self._lock:
            return {
                "blocked_count": len(blocked_domains),
                "local_record_count": len(local_records),
                "blocked_queries": self.blocked_queries,
                "recent_blocked": list(self.recent_blocked),
            }
