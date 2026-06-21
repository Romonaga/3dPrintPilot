from __future__ import annotations

from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.core.secrets import SecretCipher
from backend.domains.site_scanning.adapters.base import SiteAdapterDeclaration
from backend.domains.site_scanning.models import SiteAuthProfile
from backend.domains.site_scanning.store import SiteAuthProfileStore, mask_site_auth_secret


DECLARATIONS = [
    SiteAdapterDeclaration(
        site_key="printables",
        display_name="Printables",
        allowed_hosts=("printables.com", "www.printables.com"),
    )
]


def test_site_auth_profile_store_encrypts_and_masks_secret_values():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    _create_sqlite_site_auth_profiles_table(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    cipher = SecretCipher(Fernet.generate_key())

    with SessionLocal() as session:
        store = SiteAuthProfileStore(session, cipher)
        profile = store.upsert_profile(
            DECLARATIONS,
            site_key="printables",
            auth_mode="api_token",
            header_name="X-Api-Key",
            secret_value="site-token-1234",
            label="Personal API key",
        )
        stored = session.scalars(select(SiteAuthProfile).where(SiteAuthProfile.id == profile.id)).one()

        assert stored.encrypted_value != "site-token-1234"
        assert "site-token-1234" not in stored.encrypted_value
        assert stored.last_four == "1234"
        assert mask_site_auth_secret(stored) == "****1234"
        assert store.list_profile_statuses(DECLARATIONS)[0][1] == stored

        context = store.auth_context_for_site("printables")

        assert context.enabled is True
        assert context.headers == {"X-Api-Key": "site-token-1234"}


def test_site_auth_profile_store_builds_bearer_and_cookie_contexts():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    _create_sqlite_site_auth_profiles_table(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    cipher = SecretCipher(Fernet.generate_key())

    with SessionLocal() as session:
        store = SiteAuthProfileStore(session, cipher)
        store.upsert_profile(
            DECLARATIONS,
            site_key="printables",
            auth_mode="bearer_token",
            secret_value="bearer-secret",
        )
        assert store.auth_context_for_site("printables").headers == {"Authorization": "Bearer bearer-secret"}

        store.upsert_profile(
            DECLARATIONS,
            site_key="printables",
            auth_mode="cookie_header",
            secret_value="session=abc",
        )
        assert store.auth_context_for_site("printables").headers == {"Cookie": "session=abc"}


def test_site_auth_profile_store_supports_username_password_and_browser_session_modes():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    _create_sqlite_site_auth_profiles_table(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    cipher = SecretCipher(Fernet.generate_key())

    with SessionLocal() as session:
        store = SiteAuthProfileStore(session, cipher)
        profile = store.upsert_profile(
            DECLARATIONS,
            site_key="printables",
            auth_mode="username_password",
            account_identifier="maker@example.test",
            secret_value="printables-password-1234",
            label="Printables account",
        )
        context = store.auth_context_for_site("printables")

        assert profile.encrypted_value != "printables-password-1234"
        assert profile.account_identifier == "maker@example.test"
        assert context.enabled is True
        assert context.username == "maker@example.test"
        assert context.password == "printables-password-1234"
        assert context.headers == {}

        session_profile = store.upsert_profile(
            DECLARATIONS,
            site_key="printables",
            auth_mode="browser_session",
            account_identifier="gmail-user@example.test",
            secret_value="session=abc",
            label="Google browser session",
        )
        session_context = store.auth_context_for_site("printables")

        assert session_profile.account_identifier == "gmail-user@example.test"
        assert session_context.enabled is True
        assert session_context.headers == {"Cookie": "session=abc"}


def test_site_auth_profile_store_allows_unlinked_browser_session_without_secret_storage():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    _create_sqlite_site_auth_profiles_table(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    cipher = SecretCipher(Fernet.generate_key())

    with SessionLocal() as session:
        store = SiteAuthProfileStore(session, cipher)
        profile = store.upsert_profile(
            DECLARATIONS,
            site_key="printables",
            auth_mode="browser_session",
            account_identifier="gmail-user@example.test",
            secret_value=None,
            label="Google browser session",
        )
        context = store.auth_context_for_site("printables")

        assert profile.encrypted_value is None
        assert profile.last_four is None
        assert context.enabled is False
        assert context.headers == {}


def test_site_auth_profile_store_rejects_unknown_sites_and_unsafe_modes():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    _create_sqlite_site_auth_profiles_table(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    cipher = SecretCipher(Fernet.generate_key())

    with SessionLocal() as session:
        store = SiteAuthProfileStore(session, cipher)

        for kwargs in (
            {"site_key": "unknown", "auth_mode": "bearer_token", "secret_value": "token"},
            {"site_key": "printables", "auth_mode": "password", "secret_value": "token"},
            {"site_key": "printables", "auth_mode": "api_token", "secret_value": "token"},
            {"site_key": "printables", "auth_mode": "api_token", "header_name": "Authorization", "secret_value": "token"},
            {"site_key": "printables", "auth_mode": "bearer_token", "secret_value": ""},
            {"site_key": "printables", "auth_mode": "username_password", "secret_value": "password"},
            {"site_key": "printables", "auth_mode": "browser_session", "secret_value": "session=abc"},
            {
                "site_key": "printables",
                "auth_mode": "username_password",
                "account_identifier": "maker@example.test",
                "secret_value": "",
            },
        ):
            try:
                store.upsert_profile(DECLARATIONS, **kwargs)
            except ValueError:
                pass
            else:
                raise AssertionError(f"Expected ValueError for {kwargs}")


def test_site_auth_profile_delete_removes_context():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    _create_sqlite_site_auth_profiles_table(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    cipher = SecretCipher(Fernet.generate_key())

    with SessionLocal() as session:
        store = SiteAuthProfileStore(session, cipher)
        store.upsert_profile(
            DECLARATIONS,
            site_key="printables",
            auth_mode="bearer_token",
            secret_value="bearer-secret",
        )

        assert store.delete_profile("printables") is True
        assert store.auth_context_for_site("printables").headers == {}


def _create_sqlite_site_auth_profiles_table(engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE site_auth_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_key VARCHAR(80) NOT NULL UNIQUE,
                auth_mode VARCHAR(40) NOT NULL,
                label VARCHAR(160),
                account_identifier VARCHAR(255),
                header_name VARCHAR(120),
                encrypted_value TEXT,
                encryption_key_id VARCHAR(64),
                secret_fingerprint VARCHAR(64),
                last_four VARCHAR(8),
                enabled BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """
        )
