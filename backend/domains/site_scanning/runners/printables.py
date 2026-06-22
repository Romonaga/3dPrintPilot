from __future__ import annotations

import re
from urllib.parse import urlparse

from backend.domains.site_scanning.runners.base import (
    SourceSiteCapability,
    SourceSiteProjectRef,
    SourceSiteRunnerManifest,
    SourceSiteSupportLevel,
)
from backend.domains.site_scanning.utils import normalize_url, try_normalize_url

PRINTABLES_HOSTS = ("printables.com", "www.printables.com")
PRINTABLES_BROWSER_SESSION_HOSTS = ("api.printables.com", "printables.com", "www.printables.com")
PRINTABLES_BROWSER_SESSION_OBSERVE_HOSTS = (
    "account.prusa3d.com",
    "api.printables.com",
    "printables.com",
    "www.printables.com",
)


class PrintablesSourceSiteRunner:
    manifest = SourceSiteRunnerManifest(
        site_key="printables",
        display_name="Printables public model pages",
        support_level=SourceSiteSupportLevel.PARTIAL,
        capabilities=(
            SourceSiteCapability.PUBLIC_SCAN,
            SourceSiteCapability.ACCOUNT_SETUP,
            SourceSiteCapability.PROJECT_LOOKUP,
        ),
        allowed_hosts=PRINTABLES_HOSTS,
        url_patterns=(r"https://(?:www\.)?printables\.com/model/\d+[-/][^?#]+",),
        browser_session_hosts=PRINTABLES_BROWSER_SESSION_HOSTS,
        browser_session_observe_hosts=PRINTABLES_BROWSER_SESSION_OBSERVE_HOSTS,
        browser_session_required_cookie_names=("sessionid",),
        base_url="https://www.printables.com/",
        login_url="https://www.printables.com/login",
        setup_required=False,
        supports_downloads=False,
        supported_auth_modes=("none", "username_password", "browser_session"),
        auth_storage_notes=(
            "Email/password can be encrypted for a Printables account. Google login must use browser-assisted session "
            "linking; do not enter or store a Google password here."
        ),
        default_limits={"max_depth": 1, "max_pages": 50, "max_runtime_seconds": 300, "per_host_concurrency": 1},
        robots_terms_notes=(
            "Public metadata only. Does not sign in, bypass paywalls, evade anti-bot controls, or download model files."
        ),
    )

    def identify_project(self, url: str) -> SourceSiteProjectRef | None:
        normalized_url = try_normalize_url(url)
        if normalized_url is None:
            return None
        parsed = urlparse(normalized_url)
        if parsed.netloc.lower() not in self.manifest.allowed_hosts:
            return None
        match = re.search(r"/model/(?P<id>\d+)-(?P<slug>[^/?#]+)", parsed.path)
        if match is None:
            return None
        return SourceSiteProjectRef(
            source_url=normalize_url(f"https://www.printables.com/model/{match.group('id')}-{match.group('slug')}"),
            external_project_id=match.group("id"),
            slug=match.group("slug"),
        )
