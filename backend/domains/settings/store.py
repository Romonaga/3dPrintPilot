from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.secrets import SecretCipher
from backend.domains.settings.models import InstanceSetting, ProviderSecret

AUTH_SESSION_TIMEOUT_SETTING_KEY = "auth.session_timeout_minutes"
DEFAULT_SESSION_TIMEOUT_MINUTES = 14 * 24 * 60
MIN_SESSION_TIMEOUT_MINUTES = 5
MAX_SESSION_TIMEOUT_MINUTES = 30 * 24 * 60


@dataclass(frozen=True)
class KnownProviderSecret:
    provider: str
    secret_name: str
    label: str
    purpose: str


@dataclass(frozen=True)
class AuthSettings:
    session_timeout_minutes: int


KNOWN_PROVIDER_SECRETS = (
    KnownProviderSecret(
        provider="openai",
        secret_name="api_token",
        label="OpenAI API Token",
        purpose="Fallback model calls when local Ollama confidence is too low.",
    ),
    KnownProviderSecret(
        provider="openai",
        secret_name="account_key",
        label="OpenAI Account Key",
        purpose="Billing usage and cost reconciliation against OpenAI account data.",
    ),
)


class ProviderSecretStore:
    def __init__(self, session: Session, cipher: SecretCipher) -> None:
        self._session = session
        self._cipher = cipher

    def list_secret_statuses(self) -> list[tuple[KnownProviderSecret, ProviderSecret | None]]:
        configured = {
            (secret.provider, secret.secret_name): secret
            for secret in self._session.scalars(select(ProviderSecret)).all()
        }
        return [(known, configured.get((known.provider, known.secret_name))) for known in KNOWN_PROVIDER_SECRETS]

    def upsert_secret(self, provider: str, secret_name: str, value: str) -> ProviderSecret:
        normalized_provider, normalized_name = _normalize_secret_id(provider, secret_name)
        _require_known_secret(normalized_provider, normalized_name)
        clean_value = value.strip()
        if not clean_value:
            raise ValueError("Secret value cannot be empty")

        encrypted_value = self._cipher.encrypt(clean_value)
        now = datetime.now(UTC)
        existing = self.get_secret_record(normalized_provider, normalized_name)
        if existing is None:
            existing = ProviderSecret(
                provider=normalized_provider,
                secret_name=normalized_name,
                encrypted_value=encrypted_value,
                encryption_key_id=self._cipher.key_id,
                secret_fingerprint=self._cipher.fingerprint(clean_value),
                last_four=clean_value[-4:],
                updated_at=now,
            )
            self._session.add(existing)
        else:
            existing.encrypted_value = encrypted_value
            existing.encryption_key_id = self._cipher.key_id
            existing.secret_fingerprint = self._cipher.fingerprint(clean_value)
            existing.last_four = clean_value[-4:]
            existing.updated_at = now
        self._session.commit()
        self._session.refresh(existing)
        return existing

    def get_secret_record(self, provider: str, secret_name: str) -> ProviderSecret | None:
        normalized_provider, normalized_name = _normalize_secret_id(provider, secret_name)
        statement = select(ProviderSecret).where(
            ProviderSecret.provider == normalized_provider,
            ProviderSecret.secret_name == normalized_name,
        )
        return self._session.scalars(statement).one_or_none()

    def get_secret_value(self, provider: str, secret_name: str) -> str | None:
        record = self.get_secret_record(provider, secret_name)
        if record is None:
            return None
        return self._cipher.decrypt(record.encrypted_value)

    def delete_secret(self, provider: str, secret_name: str) -> bool:
        record = self.get_secret_record(provider, secret_name)
        if record is None:
            return False
        self._session.delete(record)
        self._session.commit()
        return True


class InstanceSettingsStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_auth_settings(self) -> AuthSettings:
        return AuthSettings(session_timeout_minutes=self.get_session_timeout_minutes())

    def update_auth_settings(self, session_timeout_minutes: int) -> AuthSettings:
        timeout = validate_session_timeout_minutes(session_timeout_minutes)
        self._upsert_setting(AUTH_SESSION_TIMEOUT_SETTING_KEY, str(timeout))
        self._session.commit()
        return AuthSettings(session_timeout_minutes=timeout)

    def get_session_timeout_minutes(self) -> int:
        setting = self._get_setting(AUTH_SESSION_TIMEOUT_SETTING_KEY)
        if setting is None:
            return DEFAULT_SESSION_TIMEOUT_MINUTES
        try:
            return validate_session_timeout_minutes(int(setting.setting_value))
        except ValueError:
            return DEFAULT_SESSION_TIMEOUT_MINUTES

    def _get_setting(self, setting_key: str) -> InstanceSetting | None:
        return self._session.scalars(
            select(InstanceSetting).where(InstanceSetting.setting_key == setting_key)
        ).one_or_none()

    def _upsert_setting(self, setting_key: str, setting_value: str) -> InstanceSetting:
        now = datetime.now(UTC)
        setting = self._get_setting(setting_key)
        if setting is None:
            setting = InstanceSetting(setting_key=setting_key, setting_value=setting_value, updated_at=now)
            self._session.add(setting)
        else:
            setting.setting_value = setting_value
            setting.updated_at = now
        return setting


def _normalize_secret_id(provider: str, secret_name: str) -> tuple[str, str]:
    return provider.strip().lower(), secret_name.strip().lower()


def _require_known_secret(provider: str, secret_name: str) -> None:
    if not any(secret.provider == provider and secret.secret_name == secret_name for secret in KNOWN_PROVIDER_SECRETS):
        raise ValueError("Unknown provider secret")


def mask_secret(record: ProviderSecret | None) -> str | None:
    if record is None:
        return None
    return f"****{record.last_four}"


def validate_session_timeout_minutes(value: int) -> int:
    if value < MIN_SESSION_TIMEOUT_MINUTES or value > MAX_SESSION_TIMEOUT_MINUTES:
        raise ValueError(
            "Session timeout must be between "
            f"{MIN_SESSION_TIMEOUT_MINUTES} and {MAX_SESSION_TIMEOUT_MINUTES} minutes"
        )
    return value
