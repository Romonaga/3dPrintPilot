from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from backend.domains.users.dependencies import extract_bearer_token, get_current_user, get_user_store
from backend.domains.users.models import User
from backend.domains.users.schemas.request import BootstrapOwnerRequest, ChangePasswordRequest, LoginRequest
from backend.domains.users.schemas.response import AuthStatusResponse, SessionResponse, UserResponse
from backend.domains.users.store import AuthError, BootstrapUnavailableError, UserStore

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=AuthStatusResponse)
def auth_status(
    authorization: Annotated[str | None, Header()] = None,
    store: UserStore = Depends(get_user_store),
) -> AuthStatusResponse:
    bootstrap_required = not store.has_users()
    token = extract_bearer_token(authorization)
    if token is None:
        return AuthStatusResponse(authenticated=False, bootstrap_required=bootstrap_required)
    user = store.get_user_for_token(token)
    if user is None:
        return AuthStatusResponse(authenticated=False, bootstrap_required=bootstrap_required)
    return AuthStatusResponse(authenticated=True, bootstrap_required=False, user=_user_response(user))


@router.post("/bootstrap", response_model=SessionResponse, status_code=201)
def bootstrap_owner(
    request: BootstrapOwnerRequest,
    store: UserStore = Depends(get_user_store),
) -> SessionResponse:
    try:
        result = store.bootstrap_owner(
            username=request.username,
            email=request.email,
            password=request.password,
            force_password_change=request.force_password_change,
        )
    except BootstrapUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _session_response(result)


@router.post("/login", response_model=SessionResponse)
def login(request: LoginRequest, store: UserStore = Depends(get_user_store)) -> SessionResponse:
    try:
        result = store.authenticate(request.username, request.password)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return _session_response(result)


@router.post("/logout", status_code=204)
def logout(
    authorization: Annotated[str | None, Header()] = None,
    store: UserStore = Depends(get_user_store),
) -> Response:
    token = extract_bearer_token(authorization)
    if token is not None:
        store.logout(token)
    return Response(status_code=204)


@router.post("/change-password", response_model=UserResponse)
def change_password(
    request: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    store: UserStore = Depends(get_user_store),
) -> UserResponse:
    try:
        updated = store.change_password(user, request.current_password, request.new_password)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _user_response(updated)


def _session_response(result) -> SessionResponse:
    return SessionResponse(
        token=result.token,
        expires_at=result.session.expires_at.isoformat(),
        user=_user_response(result.user),
    )


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        force_password_change=user.force_password_change,
        failed_login_count=user.failed_login_count,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at is not None else None,
    )
