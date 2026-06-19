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

export type ApiFetchOptions = {
  timeoutMs?: number;
};

const DEFAULT_TIMEOUT_MS = 15_000;

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit, options?: ApiFetchOptions): Promise<Response> {
  const timeoutMs = options?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const controller = new AbortController();
  const signal = init?.signal ?? controller.signal;
  const timeoutId = !init?.signal && timeoutMs > 0 ? window.setTimeout(() => controller.abort(), timeoutMs) : null;
  try {
    return await fetch(input, { ...init, headers: authHeaders(init), signal });
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error(`Request timed out after ${timeoutMs} ms`);
    }
    throw error;
  } finally {
    if (timeoutId !== null) {
      window.clearTimeout(timeoutId);
    }
  }
}
