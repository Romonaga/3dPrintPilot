from __future__ import annotations

import hashlib
import hmac
import secrets

import bcrypt


def hash_password(password: str) -> str:
    clean_password = password.encode("utf-8")
    return bcrypt.hashpw(clean_password, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_token_match(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_session_token(token), token_hash)
