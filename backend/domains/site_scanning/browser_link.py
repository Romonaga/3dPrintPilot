from __future__ import annotations

import json
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class BrowserLinkStart:
    session_id: str
    status: str
    message: str
    login_url: str
    expires_at: datetime
    cookie_count: int = 0


@dataclass(frozen=True)
class BrowserLinkStatus:
    session_id: str
    status: str
    message: str
    login_url: str
    expires_at: datetime
    cookie_header: str | None = None
    cookie_count: int = 0


@dataclass
class _BrowserLinkSession:
    session_id: str
    site_key: str
    login_url: str
    allowed_hosts: tuple[str, ...]
    capture_hosts: tuple[str, ...]
    expires_at: datetime
    work_dir: Path
    signal_file: Path
    result_file: Path
    process: subprocess.Popen | None
    status: str
    message: str


class SiteAuthBrowserLinkService:
    def __init__(self, *, repo_root: Path | None = None, timeout_seconds: int = 900) -> None:
        self._repo_root = repo_root or Path(__file__).resolve().parents[3]
        self._timeout_seconds = timeout_seconds
        self._sessions: dict[str, _BrowserLinkSession] = {}

    def start(
        self,
        *,
        site_key: str,
        login_url: str,
        allowed_hosts: tuple[str, ...],
        capture_hosts: tuple[str, ...] | None = None,
        observe_hosts: tuple[str, ...] | None = None,
        required_cookie_names: tuple[str, ...] = (),
    ) -> BrowserLinkStart:
        session_id = uuid.uuid4().hex
        work_dir = Path(tempfile.mkdtemp(prefix=f"3dprintpilot-{site_key}-link-"))
        signal_file = work_dir / "capture.json"
        result_file = work_dir / "result.json"
        expires_at = datetime.now(UTC) + timedelta(seconds=self._timeout_seconds)
        command = [
            "node",
            str(self._repo_root / "scripts" / "site-auth-browser-link.mjs"),
            "--login-url",
            login_url,
            "--allowed-hosts",
            ",".join(allowed_hosts),
            "--capture-hosts",
            ",".join(capture_hosts or allowed_hosts),
            "--observe-hosts",
            ",".join(observe_hosts or capture_hosts or allowed_hosts),
            "--required-cookie-names",
            ",".join(required_cookie_names),
            "--signal-file",
            str(signal_file),
            "--result-file",
            str(result_file),
            "--timeout-seconds",
            str(self._timeout_seconds),
        ]

        try:
            process = subprocess.Popen(
                command,
                cwd=self._repo_root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            status = "running"
            message = "Login browser launched. Complete site sign-in, then capture the signed-in session."
        except OSError as exc:
            process = None
            status = "failed"
            message = f"Login browser could not be launched: {exc}"

        self._sessions[session_id] = _BrowserLinkSession(
            session_id=session_id,
            site_key=site_key,
            login_url=login_url,
            allowed_hosts=allowed_hosts,
            capture_hosts=capture_hosts or allowed_hosts,
            expires_at=expires_at,
            work_dir=work_dir,
            signal_file=signal_file,
            result_file=result_file,
            process=process,
            status=status,
            message=message,
        )
        return BrowserLinkStart(
            session_id=session_id,
            status=status,
            message=message,
            login_url=login_url,
            expires_at=expires_at,
        )

    def request_capture(self, session_id: str) -> BrowserLinkStatus:
        session = self._require_session(session_id)
        if session.status in {"linked", "failed", "expired"}:
            return self.status(session_id)
        session.status = "capture_requested"
        session.message = "Capture requested. Waiting for the login browser to return site cookies."
        session.signal_file.write_text(json.dumps({"capture": True, "requested_at": datetime.now(UTC).isoformat()}))
        return self.status(session_id)

    def status(self, session_id: str) -> BrowserLinkStatus:
        session = self._require_session(session_id)
        now = datetime.now(UTC)
        if now > session.expires_at and session.status not in {"linked", "failed"}:
            session.status = "expired"
            session.message = "Login capture expired. Start a new browser link."
            self._terminate(session)
            return self._status(session)

        if session.result_file.exists():
            result = json.loads(session.result_file.read_text())
            if result.get("status") == "captured" and result.get("cookie_header"):
                session.status = "linked"
                session.message = "Signed-in site session captured."
                return self._status(
                    session,
                    cookie_header=str(result["cookie_header"]),
                    cookie_count=int(result.get("cookie_count") or 0),
                )
            session.status = "failed"
            session.message = str(result.get("message") or "Browser session capture failed.")
            return self._status(session)

        if session.process is not None and session.process.poll() is not None and session.status != "linked":
            session.status = "failed"
            session.message = "Login browser exited before a site session was captured."
        return self._status(session)

    def _require_session(self, session_id: str) -> _BrowserLinkSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def _status(
        self,
        session: _BrowserLinkSession,
        *,
        cookie_header: str | None = None,
        cookie_count: int = 0,
    ) -> BrowserLinkStatus:
        return BrowserLinkStatus(
            session_id=session.session_id,
            status=session.status,
            message=session.message,
            login_url=session.login_url,
            expires_at=session.expires_at,
            cookie_header=cookie_header,
            cookie_count=cookie_count,
        )

    @staticmethod
    def _terminate(session: _BrowserLinkSession) -> None:
        if session.process is not None and session.process.poll() is None:
            session.process.terminate()
