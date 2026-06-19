import { apiFetch } from "../../../lib/apiFetch";
import { type AuthSession, type AuthStatus, type AuthUser } from "../types";

type ApiUser = {
  id: number;
  username: string;
  email: string | null;
  role: string;
  is_active: boolean;
  force_password_change: boolean;
  failed_login_count: number;
  last_login_at: string | null;
};

type ApiAuthStatus = {
  authenticated: boolean;
  bootstrap_required: boolean;
  user: ApiUser | null;
};

type ApiSession = {
  token: string;
  expires_at: string;
  user: ApiUser;
};

export async function getAuthStatus(): Promise<AuthStatus> {
  const response = await apiFetch("/api/auth/me");
  if (!response.ok) {
    throw new Error(`Session check failed with HTTP ${response.status}`);
  }
  return fromApiStatus(await response.json());
}

export async function bootstrapOwner(username: string, password: string, email: string): Promise<AuthSession> {
  const response = await fetch("/api/auth/bootstrap", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, email: email.trim() || null })
  });
  if (!response.ok) {
    throw new Error(`Owner setup failed with HTTP ${response.status}`);
  }
  return fromApiSession(await response.json());
}

export async function login(username: string, password: string): Promise<AuthSession> {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password })
  });
  if (!response.ok) {
    throw new Error(`Login failed with HTTP ${response.status}`);
  }
  return fromApiSession(await response.json());
}

export async function logout(): Promise<void> {
  await apiFetch("/api/auth/logout", { method: "POST" });
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<AuthUser> {
  const response = await apiFetch("/api/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
  });
  if (!response.ok) {
    throw new Error(`Password change failed with HTTP ${response.status}`);
  }
  return fromApiUser(await response.json());
}

function fromApiStatus(status: ApiAuthStatus): AuthStatus {
  return {
    authenticated: status.authenticated,
    bootstrapRequired: status.bootstrap_required,
    user: status.user ? fromApiUser(status.user) : null
  };
}

function fromApiSession(session: ApiSession): AuthSession {
  return {
    token: session.token,
    expiresAt: session.expires_at,
    user: fromApiUser(session.user)
  };
}

function fromApiUser(user: ApiUser): AuthUser {
  return {
    id: user.id,
    username: user.username,
    email: user.email,
    role: user.role,
    isActive: user.is_active,
    forcePasswordChange: user.force_password_change,
    failedLoginCount: user.failed_login_count,
    lastLoginAt: user.last_login_at
  };
}
