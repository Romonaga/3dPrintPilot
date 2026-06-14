from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from backend.core.config import get_settings


class SecretDecryptionError(ValueError):
    """Raised when a stored secret cannot be decrypted with the active key."""


class SecretCipher:
    def __init__(self, key: bytes | str) -> None:
        key_bytes = key.encode("utf-8") if isinstance(key, str) else key
        self._key_bytes = key_bytes
        self._fernet = Fernet(key_bytes)
        self.key_id = hashlib.sha256(key_bytes).hexdigest()[:16]

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, encrypted_value: str) -> str:
        try:
            return self._fernet.decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise SecretDecryptionError("Secret cannot be decrypted with the active encryption key") from exc

    def fingerprint(self, value: str) -> str:
        message = f"provider-secret:{value}".encode("utf-8")
        return hmac.new(self._key_bytes, message, hashlib.sha256).hexdigest()


def get_secret_cipher() -> SecretCipher:
    settings = get_settings()
    key = settings.field_encryption_key or _load_or_create_key_file(settings.field_encryption_key_file)
    return SecretCipher(key)


def _load_or_create_key_file(path_value: str) -> bytes:
    key_path = Path(path_value).expanduser()
    if not key_path.is_absolute():
        key_path = Path.cwd() / key_path
    if key_path.exists():
        return key_path.read_bytes().strip()

    key_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(key_path.parent, 0o700)
    except PermissionError:
        pass
    key = Fernet.generate_key()
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(key)
    return key
