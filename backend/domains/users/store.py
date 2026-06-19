from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.domains.users.models import User, UserSession
from backend.domains.users.security import create_session_token, hash_password, hash_session_token, verify_password

ROLE_RANKS = {
    "viewer": 10,
    "user": 20,
    "admin": 30,
    "owner": 40,
}


class AuthError(Exception):
    pass


class BootstrapUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class LoginResult:
    token: str
    session: UserSession
    user: User


class UserStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def has_users(self) -> bool:
        return bool(self._session.scalar(select(func.count(User.id))))

    def bootstrap_owner(
        self,
        username: str,
        password: str,
        email: str | None = None,
        force_password_change: bool = False,
    ) -> LoginResult:
        if self.has_users():
            raise BootstrapUnavailableError("Owner bootstrap is only available before the first user exists")

        user = User(
            username=_normalize_username(username),
            email=_normalize_email(email),
            password_hash=hash_password(password),
            role="owner",
            is_active=True,
            force_password_change=force_password_change,
            failed_login_count=0,
        )
        self._session.add(user)
        self._session.flush()
        return self._create_session_for_user(user)

    def authenticate(self, username: str, password: str) -> LoginResult:
        user = self.get_user_by_username(username)
        if user is None:
            raise AuthError("Invalid username or password")
        if not user.is_active or user.disabled_at is not None:
            raise AuthError("Invalid username or password")
        if not verify_password(password, user.password_hash):
            user.failed_login_count += 1
            user.updated_at = datetime.now(UTC)
            self._session.commit()
            raise AuthError("Invalid username or password")

        user.failed_login_count = 0
        user.last_login_at = datetime.now(UTC)
        user.updated_at = user.last_login_at
        return self._create_session_for_user(user)

    def get_user_by_username(self, username: str) -> User | None:
        return self._session.scalars(select(User).where(User.username == _normalize_username(username))).one_or_none()

    def get_user_for_token(self, token: str) -> User | None:
        session = self._session.scalars(
            select(UserSession).where(
                UserSession.token_hash == hash_session_token(token),
                UserSession.expires_at > datetime.now(UTC),
            )
        ).one_or_none()
        if session is None:
            return None
        user = session.user
        if not user.is_active or user.disabled_at is not None:
            return None
        session.last_seen_at = datetime.now(UTC)
        self._session.commit()
        return user

    def logout(self, token: str) -> bool:
        result = self._session.execute(delete(UserSession).where(UserSession.token_hash == hash_session_token(token)))
        self._session.commit()
        return bool(result.rowcount)

    def change_password(self, user: User, current_password: str, new_password: str) -> User:
        if not verify_password(current_password, user.password_hash):
            raise AuthError("Current password is incorrect")
        user.password_hash = hash_password(new_password)
        user.force_password_change = False
        user.updated_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(user)
        return user

    def _create_session_for_user(self, user: User) -> LoginResult:
        token = create_session_token()
        session = UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=datetime.now(UTC) + timedelta(days=14),
        )
        self._session.add(session)
        self._session.commit()
        self._session.refresh(user)
        self._session.refresh(session)
        return LoginResult(token=token, session=session, user=user)


def role_allows(user_role: str, allowed_roles: tuple[str, ...]) -> bool:
    if user_role not in ROLE_RANKS:
        return False
    return any(user_role == role or ROLE_RANKS[user_role] >= ROLE_RANKS.get(role, 10_000) for role in allowed_roles)


def _normalize_username(username: str) -> str:
    clean_username = username.strip().lower()
    if not clean_username:
        raise ValueError("Username is required")
    return clean_username


def _normalize_email(email: str | None) -> str | None:
    if email is None:
        return None
    clean_email = email.strip().lower()
    return clean_email or None
