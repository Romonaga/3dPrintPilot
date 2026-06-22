from __future__ import annotations

from threading import Lock
from time import monotonic, sleep
from urllib.parse import urlparse


class SourceSiteRequestThrottler:
    def __init__(
        self,
        *,
        default_min_interval_seconds: float = 1.0,
        clock=monotonic,
        sleeper=sleep,
    ) -> None:
        self._default_min_interval_seconds = max(0.0, float(default_min_interval_seconds))
        self._clock = clock
        self._sleeper = sleeper
        self._next_allowed_by_host: dict[str, float] = {}
        self._lock = Lock()

    def wait(self, url: str, *, min_interval_seconds: float | None = None) -> None:
        host = urlparse(url).netloc.lower()
        if not host:
            return
        interval = self._default_min_interval_seconds if min_interval_seconds is None else max(0.0, float(min_interval_seconds))
        if interval <= 0:
            return

        with self._lock:
            now = self._clock()
            next_allowed = self._next_allowed_by_host.get(host, now)
            delay = max(0.0, next_allowed - now)
            self._next_allowed_by_host[host] = max(now, next_allowed) + interval

        if delay > 0:
            self._sleeper(delay)


source_site_request_throttler = SourceSiteRequestThrottler()
