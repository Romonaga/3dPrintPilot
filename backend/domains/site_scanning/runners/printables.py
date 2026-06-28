from __future__ import annotations

from pathlib import PurePath
import re
from urllib.parse import urlparse

import httpx

from backend.domains.site_scanning.runners.base import (
    SourceSiteCapability,
    SourceSiteDownloadedFile,
    SourceSiteFile,
    SourceSiteProjectFiles,
    SourceSiteProjectRef,
    SourceSiteRunnerError,
    SourceSiteRunnerManifest,
    SourceSiteSupportLevel,
)
from backend.domains.site_scanning.runners.throttle import source_site_request_throttler
from backend.domains.site_scanning.utils import normalize_url, try_normalize_url

PRINTABLES_HOSTS = ("printables.com", "www.printables.com")
PRINTABLES_BROWSER_SESSION_HOSTS = ("api.printables.com", "printables.com", "www.printables.com")
PRINTABLES_BROWSER_SESSION_OBSERVE_HOSTS = (
    "account.prusa3d.com",
    "api.printables.com",
    "printables.com",
    "www.printables.com",
)
PRINTABLES_GRAPHQL_URL = "https://api.printables.com/graphql/"
PRINTABLES_FILES_HOST = "files.printables.com"
PRINTABLES_REQUEST_MIN_INTERVAL_SECONDS = 1.0
PRINTABLES_DOWNLOAD_PACK_FILE_ID_PREFIX = "download-pack:"
SUPPORTED_MODEL_EXTENSIONS = {".stl": "stl", ".3mf": "3mf"}
GENERIC_DOWNLOAD_PACK_NAMES = {"download all files", "all files", "download files"}
DOWNLOAD_PACK_LABELS_BY_FILE_TYPE = {
    "3mf": "All model files",
    "model": "All model files",
    "model_file": "All model files",
    "model_files": "All model files",
    "models": "All model files",
    "stl": "All model files",
    "stls": "All model files",
    "g_code": "All print files",
    "g_codes": "All print files",
    "gcode": "All print files",
    "gcodes": "All print files",
    "print": "All print files",
    "print_file": "All print files",
    "print_files": "All print files",
    "prints": "All print files",
}
MODEL_FILES_QUERY = """
query ModelFiles($id: ID!) {
  model: print(id: $id) {
    id
    name
    stls {
      id
      created
      name
      folder
      note
      fileSize
      order
    }
    downloadPacks {
      id
      name
      fileSize
      fileType
    }
  }
}
"""
DOWNLOAD_LINK_MUTATION = """
mutation GetDownloadLink($id: ID!, $modelId: ID!, $fileType: DownloadFileTypeEnum!, $source: DownloadSourceEnum!) {
  getDownloadLink(
    id: $id
    printId: $modelId
    fileType: $fileType
    source: $source
  ) {
    ok
    errors {
      field
      messages
    }
    output {
      link
      count
      ttl
    }
  }
}
"""


class PrintablesSourceSiteRunner:
    manifest = SourceSiteRunnerManifest(
        site_key="printables",
        display_name="Printables public model pages",
        support_level=SourceSiteSupportLevel.PARTIAL,
        capabilities=(
            SourceSiteCapability.PUBLIC_SCAN,
            SourceSiteCapability.ACCOUNT_SETUP,
            SourceSiteCapability.PROJECT_LOOKUP,
            SourceSiteCapability.FILE_LISTING,
            SourceSiteCapability.FILE_DOWNLOAD,
        ),
        allowed_hosts=PRINTABLES_HOSTS,
        url_patterns=(r"https://(?:www\.)?printables\.com/model/\d+[-/][^?#]+",),
        browser_session_hosts=PRINTABLES_BROWSER_SESSION_HOSTS,
        browser_session_observe_hosts=PRINTABLES_BROWSER_SESSION_OBSERVE_HOSTS,
        browser_session_required_cookie_names=("sessionid",),
        base_url="https://www.printables.com/",
        login_url="https://www.printables.com/login",
        setup_required=False,
        supports_downloads=True,
        supported_auth_modes=("none", "username_password", "browser_session"),
        auth_storage_notes=(
            "Email/password can be encrypted for a Printables account. Google login must use browser-assisted session "
            "linking; do not enter or store a Google password here."
        ),
        default_limits={"max_depth": 1, "max_pages": 50, "max_runtime_seconds": 300, "per_host_concurrency": 1},
        robots_terms_notes=(
            "Uses Printables project file metadata and normal download-link generation. Does not bypass paywalls, "
            "site controls, or anti-bot challenges."
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

    def list_project_files(
        self,
        project_url: str,
        *,
        auth_headers: dict[str, str] | None = None,
    ) -> SourceSiteProjectFiles:
        project = self._require_project(project_url)
        payload = _post_graphql(
            MODEL_FILES_QUERY,
            {"id": project.external_project_id},
            auth_headers=auth_headers,
        )
        model = ((payload.get("data") or {}).get("model") or {})
        if str(model.get("id") or "") != project.external_project_id:
            raise SourceSiteRunnerError("Printables project files could not be resolved for that URL.")
        model_files = tuple(
            _source_file(project, raw_file)
            for raw_file in sorted(model.get("stls") or [], key=lambda item: item.get("order") or 0)
        )
        files = model_files
        if not files:
            files = tuple(_source_download_pack(project, raw_pack) for raw_pack in model.get("downloadPacks") or [])
        if not files:
            raise SourceSiteRunnerError("Printables did not return any model files for that project.")
        return SourceSiteProjectFiles(
            site_key=self.manifest.site_key,
            source_project_url=project.source_url,
            external_project_id=project.external_project_id or "",
            project_title=str(model.get("name") or "").strip() or None,
            files=files,
        )

    def download_project_file(
        self,
        project_url: str,
        file_id: str,
        *,
        auth_headers: dict[str, str] | None = None,
        max_bytes: int,
    ) -> SourceSiteDownloadedFile:
        project_files = self.list_project_files(project_url, auth_headers=auth_headers)
        source_file = next((item for item in project_files.files if item.file_id == str(file_id)), None)
        if source_file is None:
            raise SourceSiteRunnerError("Selected Printables file was not found on that project.")
        if _is_download_pack_file_id(source_file.file_id):
            pack_id, file_type = _download_pack_link_parts(source_file.file_id)
            link = self._download_link(project_files.external_project_id, pack_id, auth_headers, file_type=file_type)
            parsed_link = urlparse(link)
            if parsed_link.scheme != "https" or parsed_link.netloc.lower() != PRINTABLES_FILES_HOST:
                raise SourceSiteRunnerError("Printables returned an unexpected download host.")
            data, content_type = _download_bytes(link, auth_headers=auth_headers, max_bytes=max_bytes)
            return SourceSiteDownloadedFile(
                file_id=source_file.file_id,
                filename=source_file.filename,
                content_type=content_type,
                data=data,
                source_project_url=project_files.source_project_url,
                source_file_url=link,
            )
        if not source_file.supported_model_file:
            raise SourceSiteRunnerError("Selected Printables file is not an STL or 3MF model file.")
        link = self._download_link(project_files.external_project_id, source_file.file_id, auth_headers)
        parsed_link = urlparse(link)
        if parsed_link.scheme != "https" or parsed_link.netloc.lower() != PRINTABLES_FILES_HOST:
            raise SourceSiteRunnerError("Printables returned an unexpected download host.")
        data, content_type = _download_bytes(link, auth_headers=auth_headers, max_bytes=max_bytes)
        return SourceSiteDownloadedFile(
            file_id=source_file.file_id,
            filename=source_file.filename,
            content_type=content_type,
            data=data,
            source_project_url=project_files.source_project_url,
            source_file_url=link,
        )

    def _download_link(
        self,
        model_id: str,
        file_id: str,
        auth_headers: dict[str, str] | None,
        *,
        file_type: str = "stl",
    ) -> str:
        payload = _post_graphql(
            DOWNLOAD_LINK_MUTATION,
            {
                "id": str(file_id),
                "modelId": str(model_id),
                "fileType": file_type,
                "source": "model_detail",
            },
            auth_headers=auth_headers,
        )
        result = ((payload.get("data") or {}).get("getDownloadLink") or {})
        output = result.get("output") or {}
        link = str(output.get("link") or "").strip()
        if not result.get("ok") or not link:
            messages = [
                str(message)
                for error in result.get("errors") or []
                for message in (error.get("messages") or [])
            ]
            detail = "; ".join(messages) or "Printables did not return a download link."
            raise SourceSiteRunnerError(detail)
        return link

    def _require_project(self, project_url: str) -> SourceSiteProjectRef:
        project = self.identify_project(project_url)
        if project is None or project.external_project_id is None:
            raise SourceSiteRunnerError("Enter a supported Printables model URL.")
        return project


def _source_file(project: SourceSiteProjectRef, raw_file: dict) -> SourceSiteFile:
    filename = str(raw_file.get("name") or "").strip()
    suffix = PurePath(filename).suffix.lower()
    file_format = SUPPORTED_MODEL_EXTENSIONS.get(suffix, suffix.lstrip(".") or "unknown")
    file_id = str(raw_file.get("id") or "").strip()
    supported = suffix in SUPPORTED_MODEL_EXTENSIONS and bool(file_id)
    return SourceSiteFile(
        file_id=file_id,
        filename=filename or f"printables-file-{file_id}",
        file_format=file_format,
        size_bytes=_optional_int(raw_file.get("fileSize")),
        source_file_url=f"{project.source_url}/files#file-{file_id}",
        supported_model_file=supported,
        created_at=str(raw_file.get("created") or "").strip() or None,
        notes=str(raw_file.get("note") or "").strip() or None,
    )


def _source_download_pack(project: SourceSiteProjectRef, raw_pack: dict) -> SourceSiteFile:
    pack_id = str(raw_pack.get("id") or "").strip()
    file_type = str(raw_pack.get("fileType") or "zip").strip() or "zip"
    name = _download_pack_label(raw_pack)
    filename = name if PurePath(name).suffix.lower() == ".zip" else f"{name}.zip"
    return SourceSiteFile(
        file_id=f"{PRINTABLES_DOWNLOAD_PACK_FILE_ID_PREFIX}{pack_id}:{file_type}",
        filename=filename,
        file_format="zip",
        size_bytes=_optional_int(raw_pack.get("fileSize")),
        source_file_url=f"{project.source_url}/files#download-pack-{pack_id}",
        supported_model_file=bool(pack_id),
        notes="Printables download-all archive; supported STL and 3MF files will be imported.",
    )


def _download_pack_label(raw_pack: dict) -> str:
    name = str(raw_pack.get("name") or "").strip()
    if name and name.casefold() not in GENERIC_DOWNLOAD_PACK_NAMES:
        return name
    file_type = _normalize_download_pack_file_type(raw_pack.get("fileType"))
    if label := DOWNLOAD_PACK_LABELS_BY_FILE_TYPE.get(file_type):
        return label
    return _fallback_download_pack_label(file_type=file_type, pack_id=str(raw_pack.get("id") or "").strip())


def _normalize_download_pack_file_type(value: object) -> str:
    raw_value = str(value or "").strip()
    snake_value = re.sub(r"(?<!^)(?=[A-Z])", "_", raw_value)
    return re.sub(r"[^a-z0-9]+", "_", snake_value.casefold()).strip("_")


def _fallback_download_pack_label(*, file_type: str, pack_id: str) -> str:
    base = "Download archive"
    if file_type and file_type != "zip":
        base = f"Download {file_type.replace('_', ' ')} archive"
    return f"{base} {pack_id}" if pack_id else base


def _is_download_pack_file_id(file_id: str) -> bool:
    return file_id.startswith(PRINTABLES_DOWNLOAD_PACK_FILE_ID_PREFIX)


def _download_pack_link_parts(file_id: str) -> tuple[str, str]:
    raw_value = file_id.removeprefix(PRINTABLES_DOWNLOAD_PACK_FILE_ID_PREFIX)
    pack_id, _, file_type = raw_value.partition(":")
    if not pack_id:
        raise SourceSiteRunnerError("Selected Printables download pack is invalid.")
    return pack_id, file_type or "zip"


def _post_graphql(query: str, variables: dict, *, auth_headers: dict[str, str] | None = None) -> dict:
    headers = _request_headers(auth_headers)
    headers["Content-Type"] = "application/json"
    try:
        _throttle_request(PRINTABLES_GRAPHQL_URL)
        with httpx.Client(headers=headers, follow_redirects=True, timeout=20) as client:
            response = client.post(PRINTABLES_GRAPHQL_URL, json={"query": query, "variables": variables})
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SourceSiteRunnerError("Printables file metadata request failed.") from exc
    if payload.get("errors"):
        messages = [
            str(message)
            for error in payload.get("errors") or []
            for message in (error.get("messages") or [error.get("message")])
            if message
        ]
        raise SourceSiteRunnerError("; ".join(messages) or "Printables returned a GraphQL error.")
    return payload


def _download_bytes(url: str, *, auth_headers: dict[str, str] | None = None, max_bytes: int) -> tuple[bytes, str | None]:
    data = bytearray()
    try:
        _throttle_request(url)
        with httpx.Client(headers=_request_headers(auth_headers), follow_redirects=True, timeout=45) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                if response.url.scheme != "https" or response.url.host != PRINTABLES_FILES_HOST:
                    raise SourceSiteRunnerError("Printables download redirected to an unexpected host.")
                content_type = response.headers.get("content-type")
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        raise SourceSiteRunnerError("Downloaded Printables file exceeds the model import limit.")
    except httpx.HTTPError as exc:
        raise SourceSiteRunnerError("Printables file download failed.") from exc
    return bytes(data), content_type


def _request_headers(auth_headers: dict[str, str] | None) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.printables.com",
        "Referer": "https://www.printables.com/",
        "User-Agent": "3dPrintPilot/0.1 local source site runner",
    }
    headers.update(auth_headers or {})
    return headers


def _throttle_request(url: str) -> None:
    source_site_request_throttler.wait(url, min_interval_seconds=PRINTABLES_REQUEST_MIN_INTERVAL_SECONDS)


def _optional_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
