from __future__ import annotations

from backend.domains.site_scanning.runners.throttle import SourceSiteRequestThrottler


def test_source_site_throttler_spaces_requests_per_host_without_real_sleep():
    now = [100.0]
    sleeps: list[float] = []

    def clock() -> float:
        return now[0]

    def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    throttler = SourceSiteRequestThrottler(default_min_interval_seconds=1.25, clock=clock, sleeper=sleeper)

    throttler.wait("https://api.printables.com/graphql/")
    throttler.wait("https://api.printables.com/graphql/")
    throttler.wait("https://files.printables.com/media/model.stl")
    throttler.wait("https://api.printables.com/other")

    assert sleeps == [1.25, 1.25]


def test_source_site_throttler_can_be_disabled_for_a_call():
    sleeps: list[float] = []
    throttler = SourceSiteRequestThrottler(default_min_interval_seconds=1.0, clock=lambda: 10.0, sleeper=sleeps.append)

    throttler.wait("https://api.printables.com/graphql/")
    throttler.wait("https://api.printables.com/graphql/", min_interval_seconds=0)

    assert sleeps == []
