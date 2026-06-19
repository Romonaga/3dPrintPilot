from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db_session
from backend.domains.users.models import User
from backend.domains.users.store import UserStore, role_allows


def get_user_store(session: Session = Depends(get_db_session)) -> UserStore:
    return UserStore(session)


def extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    store: UserStore = Depends(get_user_store),
) -> User:
    token = extract_bearer_token(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = store.get_user_for_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


def require_roles(*allowed_roles: str) -> Callable:
    def dependency(
        authorization: Annotated[str | None, Header()] = None,
        store: UserStore = Depends(get_user_store),
    ) -> User | None:
        if not store.has_users():
            return None

        token = extract_bearer_token(authorization)
        if token is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        user = store.get_user_for_token(token)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        if not role_allows(user.role, allowed_roles):
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return dependency
