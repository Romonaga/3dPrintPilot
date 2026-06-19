from __future__ import annotations

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None
    role: str
    is_active: bool
    force_password_change: bool
    failed_login_count: int
    last_login_at: str | None


class SessionResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    expires_at: str
    user: UserResponse


class AuthStatusResponse(BaseModel):
    authenticated: bool
    bootstrap_required: bool
    user: UserResponse | None = None
