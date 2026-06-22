from __future__ import annotations

from collections.abc import Iterable

from backend.domains.site_scanning.runners.base import SourceSiteRunner, SourceSiteRunnerManifest
from backend.domains.site_scanning.runners.printables import PrintablesSourceSiteRunner


class SourceSiteRunnerRegistry:
    def __init__(self, runners: Iterable[SourceSiteRunner]) -> None:
        self._runners = {runner.manifest.site_key: runner for runner in runners}

    def list_runners(self) -> list[SourceSiteRunner]:
        return list(self._runners.values())

    def list_manifests(self) -> list[SourceSiteRunnerManifest]:
        return [runner.manifest for runner in self.list_runners()]

    def get(self, site_key: str) -> SourceSiteRunner | None:
        return self._runners.get(site_key)

    def manifest_for(self, site_key: str) -> SourceSiteRunnerManifest | None:
        runner = self.get(site_key)
        return runner.manifest if runner is not None else None


def default_runner_registry() -> SourceSiteRunnerRegistry:
    return SourceSiteRunnerRegistry([PrintablesSourceSiteRunner()])
