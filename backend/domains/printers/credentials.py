from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.secrets import SecretCipher
from backend.domains.printers.models import Printer
from backend.domains.settings.models import ProviderSecret

PRINTER_SECRET_PROVIDER = "printer"


def bambu_lan_secret_name(printer_id: int) -> str:
    return f"printer_{printer_id}_bambu_lan"


def configure_bambu_lan_credentials(
    session: Session,
    cipher: SecretCipher,
    printer: Printer,
    access_code: str,
    device_id: str,
) -> Printer:
    clean_access_code = _clean_required_value(access_code, "Bambu LAN access code")
    clean_device_id = _clean_required_value(device_id, "Bambu device ID")
    secret_name = bambu_lan_secret_name(printer.id)
    encrypted_value = cipher.encrypt(clean_access_code)
    now = datetime.now(UTC)
    secret = _get_printer_secret_record(session, secret_name)
    if secret is None:
        secret = ProviderSecret(
            provider=PRINTER_SECRET_PROVIDER,
            secret_name=secret_name,
            encrypted_value=encrypted_value,
            encryption_key_id=cipher.key_id,
            secret_fingerprint=cipher.fingerprint(clean_access_code),
            last_four=clean_access_code[-4:],
            updated_at=now,
        )
        session.add(secret)
    else:
        secret.encrypted_value = encrypted_value
        secret.encryption_key_id = cipher.key_id
        secret.secret_fingerprint = cipher.fingerprint(clean_access_code)
        secret.last_four = clean_access_code[-4:]
        secret.updated_at = now

    printer.credential_secret_name = secret_name
    printer.capabilities = {**(printer.capabilities or {}), "device_id": clean_device_id}
    session.commit()
    session.refresh(printer)
    return printer


def get_bambu_lan_access_code(session: Session, cipher: SecretCipher, printer: Printer) -> str | None:
    secret_name = getattr(printer, "credential_secret_name", None)
    if not secret_name:
        return None
    secret = _get_printer_secret_record(session, secret_name)
    if secret is None:
        return None
    return cipher.decrypt(secret.encrypted_value)


def delete_bambu_lan_credentials(session: Session, printer: Printer) -> bool:
    secret_name = getattr(printer, "credential_secret_name", None)
    deleted = False
    if secret_name:
        secret = _get_printer_secret_record(session, secret_name)
        if secret is not None:
            session.delete(secret)
            deleted = True
    printer.credential_secret_name = None
    capabilities = dict(printer.capabilities or {})
    capabilities.pop("device_id", None)
    printer.capabilities = capabilities
    session.commit()
    session.refresh(printer)
    return deleted


def _get_printer_secret_record(session: Session, secret_name: str) -> ProviderSecret | None:
    return session.scalars(
        select(ProviderSecret).where(
            ProviderSecret.provider == PRINTER_SECRET_PROVIDER,
            ProviderSecret.secret_name == secret_name,
        )
    ).one_or_none()


def _clean_required_value(value: str, label: str) -> str:
    clean_value = value.strip()
    if not clean_value:
        raise ValueError(f"{label} cannot be empty")
    if "\x00" in clean_value:
        raise ValueError(f"{label} contains invalid characters")
    return clean_value
