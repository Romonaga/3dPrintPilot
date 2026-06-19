import { useCallback, useEffect, useState } from "react";
import { clearStoredAuthToken, storeAuthToken } from "../../../lib/apiFetch";
import { bootstrapOwner, changePassword, getAuthStatus, login, logout } from "../api/authApi";
import { type AuthUser } from "../types";

export function useAuthSession() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [bootstrapRequired, setBootstrapRequired] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const status = await getAuthStatus();
      setBootstrapRequired(status.bootstrapRequired);
      setUser(status.user);
      if (!status.authenticated) {
        clearStoredAuthToken();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Session check failed");
      clearStoredAuthToken();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function bootstrap(username: string, password: string, email: string) {
    setError(null);
    const session = await bootstrapOwner(username, password, email);
    storeAuthToken(session.token);
    setBootstrapRequired(false);
    setUser(session.user);
  }

  async function signIn(username: string, password: string) {
    setError(null);
    const session = await login(username, password);
    storeAuthToken(session.token);
    setBootstrapRequired(false);
    setUser(session.user);
  }

  async function signOut() {
    await logout();
    clearStoredAuthToken();
    setUser(null);
  }

  async function updatePassword(currentPassword: string, newPassword: string) {
    setError(null);
    const updatedUser = await changePassword(currentPassword, newPassword);
    setUser(updatedUser);
  }

  return {
    user,
    bootstrapRequired,
    isLoading,
    error,
    bootstrap,
    signIn,
    signOut,
    updatePassword,
    refresh
  };
}
