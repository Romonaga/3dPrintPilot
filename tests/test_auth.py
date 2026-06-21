from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import create_app
from backend.domains.users.dependencies import get_user_store
from backend.domains.users.models import User, UserSession
from backend.domains.users.security import hash_password
from backend.domains.users.store import UserStore


def test_bootstrap_login_me_logout_and_token_hashing():
    client, SessionLocal = _auth_client()

    bootstrap_response = client.post(
        "/api/auth/bootstrap",
        json={"username": "Owner", "email": "Owner@Example.test", "password": "correct-password"},
    )

    assert bootstrap_response.status_code == 201
    body = bootstrap_response.json()
    token = body["token"]
    assert body["user"]["username"] == "owner"
    assert body["user"]["role"] == "owner"
    with SessionLocal() as session:
        stored_session = session.scalars(select(UserSession)).one()
        assert stored_session.token_hash != token
        assert len(stored_session.token_hash) == 64

    second_bootstrap = client.post(
        "/api/auth/bootstrap",
        json={"username": "second", "password": "correct-password"},
    )
    assert second_bootstrap.status_code == 409

    failed_login = client.post("/api/auth/login", json={"username": "owner", "password": "wrong"})
    assert failed_login.status_code == 401
    with SessionLocal() as session:
        assert session.scalars(select(User).where(User.username == "owner")).one().failed_login_count == 1

    login_response = client.post("/api/auth/login", json={"username": "owner", "password": "correct-password"})
    assert login_response.status_code == 200
    login_token = login_response.json()["token"]

    me_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {login_token}"})
    assert me_response.status_code == 200
    assert me_response.json()["authenticated"] is True
    assert me_response.json()["user"]["failed_login_count"] == 0
    assert me_response.json()["user"]["last_login_at"] is not None

    logout_response = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {login_token}"})
    assert logout_response.status_code == 204
    after_logout = client.get("/api/auth/me", headers={"Authorization": f"Bearer {login_token}"})
    assert after_logout.json()["authenticated"] is False


def test_disabled_users_and_force_password_change_are_enforced():
    client, SessionLocal = _auth_client()

    client.post("/api/auth/bootstrap", json={"username": "owner", "password": "correct-password"})
    with SessionLocal() as session:
        disabled = User(
            username="disabled",
            password_hash=hash_password("correct-password"),
            role="user",
            is_active=False,
        )
        forced = User(
            username="forced",
            password_hash=hash_password("old-password"),
            role="admin",
            is_active=True,
            force_password_change=True,
        )
        session.add_all([disabled, forced])
        session.commit()

    disabled_login = client.post("/api/auth/login", json={"username": "disabled", "password": "correct-password"})
    assert disabled_login.status_code == 401

    forced_login = client.post("/api/auth/login", json={"username": "forced", "password": "old-password"})
    assert forced_login.status_code == 200
    token = forced_login.json()["token"]
    assert forced_login.json()["user"]["force_password_change"] is True

    change_response = client.post(
        "/api/auth/change-password",
        json={"current_password": "old-password", "new_password": "new-password"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert change_response.status_code == 200
    assert change_response.json()["force_password_change"] is False
    assert client.post("/api/auth/login", json={"username": "forced", "password": "new-password"}).status_code == 200


def test_protected_routes_require_sessions_and_roles_once_users_exist():
    client, SessionLocal = _auth_client()

    owner_token = client.post(
        "/api/auth/bootstrap",
        json={"username": "owner", "password": "correct-password"},
    ).json()["token"]
    with SessionLocal() as session:
        viewer = User(username="viewer", password_hash=hash_password("correct-password"), role="viewer", is_active=True)
        session.add(viewer)
        session.commit()

    unauthenticated = client.get("/api/settings/provider-secrets")
    assert unauthenticated.status_code == 401

    viewer_token = client.post("/api/auth/login", json={"username": "viewer", "password": "correct-password"}).json()[
        "token"
    ]
    forbidden = client.get("/api/settings/provider-secrets", headers={"Authorization": f"Bearer {viewer_token}"})
    assert forbidden.status_code == 403

    owner_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
    assert owner_me.status_code == 200
    assert owner_me.json()["user"]["role"] == "owner"


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("POST", "/api/printers/scan", {"scan_method": "http", "max_hosts": 1, "ports": [80]}),
        ("POST", "/api/printers/12/print/start", {"filename": "cube.gcode"}),
        ("POST", "/api/printers/12/print/pause", None),
        ("POST", "/api/printers/12/print/resume", None),
        ("POST", "/api/printers/12/print/cancel", None),
        ("POST", "/api/site-scanning/scans", {"url": "https://example.com/models/cube"}),
        ("POST", "/api/resources/samples", None),
        ("GET", "/api/settings/provider-secrets", None),
        (
            "POST",
            "/api/ai/accounting/reconcile/openai",
            {"period_start": "2026-06-01T00:00:00Z", "period_end": "2026-06-02T00:00:00Z"},
        ),
        ("GET", "/api/operations/backup.json", None),
    ],
)
def test_sensitive_routes_block_anonymous_and_low_privilege_users(method: str, path: str, payload: dict | None):
    client, SessionLocal = _auth_client()

    client.post("/api/auth/bootstrap", json={"username": "owner", "password": "correct-password"})
    with SessionLocal() as session:
        viewer = User(username="viewer", password_hash=hash_password("correct-password"), role="viewer", is_active=True)
        session.add(viewer)
        session.commit()
    viewer_token = client.post("/api/auth/login", json={"username": "viewer", "password": "correct-password"}).json()[
        "token"
    ]

    request_kwargs = {"json": payload} if payload is not None else {}
    anonymous = client.request(method, path, **request_kwargs)
    low_privilege = client.request(
        method,
        path,
        headers={"Authorization": f"Bearer {viewer_token}"},
        **request_kwargs,
    )

    assert anonymous.status_code == 401
    assert low_privilege.status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/api/printers",
        "/api/printers/12/files",
        "/api/printers/12/job-status",
        "/api/resources/status",
        "/api/site-scanning/adapters",
        "/api/models",
    ],
)
def test_read_routes_block_anonymous_users_after_bootstrap(path: str):
    client, _SessionLocal = _auth_client()

    client.post("/api/auth/bootstrap", json={"username": "owner", "password": "correct-password"})

    response = client.get(path)

    assert response.status_code == 401


def _auth_client() -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    _create_sqlite_auth_tables(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    app = create_app()

    def user_store_override() -> Generator[UserStore, None, None]:
        with SessionLocal() as session:
            yield UserStore(session)

    app.dependency_overrides[get_user_store] = user_store_override
    return TestClient(app), SessionLocal


def _create_sqlite_auth_tables(engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(80) NOT NULL UNIQUE,
                email VARCHAR(255),
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(32) NOT NULL DEFAULT 'user',
                is_active BOOLEAN NOT NULL DEFAULT 1,
                force_password_change BOOLEAN NOT NULL DEFAULT 0,
                failed_login_count INTEGER NOT NULL DEFAULT 0,
                last_login_at DATETIME,
                disabled_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """
        )
        connection.exec_driver_sql("CREATE INDEX ix_users_is_active ON users (is_active)")
        connection.exec_driver_sql(
            """
            CREATE TABLE user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash VARCHAR(128) NOT NULL UNIQUE,
                expires_at DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """
        )
        connection.exec_driver_sql("CREATE INDEX ix_user_sessions_user_id ON user_sessions (user_id)")
