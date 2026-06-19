import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, AUTH_TOKEN_STORAGE_KEY } from "./apiFetch";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("apiFetch", () => {
  it("preserves auth headers while adding timeout-capable signals", async () => {
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, "session-token");
    const fetchMock = vi.fn(() => Promise.resolve(new Response("{}", { status: 200 })));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/example", { headers: { "X-Test": "yes" } });

    const [, init] = fetchMock.mock.calls[0] as unknown as [RequestInfo | URL, RequestInit];
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer session-token");
    expect(headers.get("X-Test")).toBe("yes");
    expect(init?.signal).toBeInstanceOf(AbortSignal);
  });

  it("rejects timed out requests with a clear error", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn((_input, init?: RequestInit) => {
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
        });
      })
    );

    const request = apiFetch("/api/slow", undefined, { timeoutMs: 25 });
    const expectation = expect(request).rejects.toThrow("Request timed out after 25 ms");
    await vi.advanceTimersByTimeAsync(25);

    await expectation;
  });
});
