from __future__ import annotations

import hashlib

from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.core.secrets import SecretCipher
from backend.domains.settings.models import ProviderSecret
from backend.domains.settings.store import ProviderSecretStore, mask_secret


def test_secret_cipher_round_trips_without_returning_plaintext_ciphertext():
    cipher = SecretCipher(Fernet.generate_key())
    secret = "sk-test-secret-value"

    encrypted = cipher.encrypt(secret)

    assert encrypted != secret
    assert secret not in encrypted
    assert cipher.decrypt(encrypted) == secret


def test_provider_secret_store_encrypts_openai_token_in_database():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    _create_sqlite_provider_secrets_table(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    cipher = SecretCipher(Fernet.generate_key())

    with SessionLocal() as session:
        store = ProviderSecretStore(session, cipher)
        record = store.upsert_secret("openai", "api_token", "sk-test-token-1234")
        stored = session.scalars(select(ProviderSecret).where(ProviderSecret.id == record.id)).one()

        assert stored.encrypted_value != "sk-test-token-1234"
        assert "sk-test-token-1234" not in stored.encrypted_value
        assert stored.secret_fingerprint != hashlib.sha256(b"sk-test-token-1234").hexdigest()
        assert stored.last_four == "1234"
        assert mask_secret(stored) == "****1234"
        assert store.get_secret_value("openai", "api_token") == "sk-test-token-1234"


def test_provider_secret_store_tracks_openai_account_key_separately():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    _create_sqlite_provider_secrets_table(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    cipher = SecretCipher(Fernet.generate_key())

    with SessionLocal() as session:
        store = ProviderSecretStore(session, cipher)
        store.upsert_secret("openai", "api_token", "sk-test-token-1234")
        store.upsert_secret("openai", "account_key", "ak-test-account-5678")

        assert store.get_secret_value("openai", "api_token") == "sk-test-token-1234"
        assert store.get_secret_value("openai", "account_key") == "ak-test-account-5678"


def _create_sqlite_provider_secrets_table(engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE provider_secrets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider VARCHAR(40) NOT NULL,
                secret_name VARCHAR(80) NOT NULL,
                encrypted_value TEXT NOT NULL,
                encryption_key_id VARCHAR(64) NOT NULL,
                secret_fingerprint VARCHAR(64) NOT NULL,
                last_four VARCHAR(8) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                CONSTRAINT uq_provider_secrets_provider_secret_name UNIQUE (provider, secret_name)
            )
            """
        )
