export const AUTH_TOKEN_STORAGE_KEY = "printpilot.auth.token";

export function getStoredAuthToken(): string | null {
  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
}

export function storeAuthToken(token: string) {
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
}

export function clearStoredAuthToken() {
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
}

export function authHeaders(init?: RequestInit): Headers {
  const headers = new Headers(init?.headers);
  const token = getStoredAuthToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

export function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  return fetch(input, { ...init, headers: authHeaders(init) });
}
