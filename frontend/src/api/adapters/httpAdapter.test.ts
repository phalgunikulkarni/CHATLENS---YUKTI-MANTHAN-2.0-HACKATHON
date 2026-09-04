import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import fc from "fast-check";
import { HttpAdapter } from "./httpAdapter";
import { clearAccountId, setAccountId } from "../accountContext";

/**
 * Feature: account-scoped-chat-and-isolation (Phase A).
 * Property 2: Frontend attaches the signed-in account id to every user-owned request.
 * Validates: Requirements R1.1, R1.2, R1.5.
 *
 * A fake `fetch` captures the outbound headers so we can assert the
 * `X-Account-Id` header equals the holder value, that no header is sent when
 * signed out, and that base URL / Content-Type behavior is preserved.
 */

const BASE = "http://api.test";

type Captured = { url: string; init?: RequestInit };
let captured: Captured[] = [];

function fakeFetch(ok = true, body: unknown = {}) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    captured.push({ url, init });
    return {
      ok,
      status: ok ? 200 : 500,
      json: async () => body,
    } as unknown as Response;
  });
}

function headersOf(init?: RequestInit): Record<string, string> {
  return (init?.headers ?? {}) as Record<string, string>;
}

beforeEach(() => {
  captured = [];
  clearAccountId();
});

afterEach(() => {
  clearAccountId();
  vi.restoreAllMocks();
});

describe("HttpAdapter X-Account-Id injection", () => {
  it("POST carries X-Account-Id equal to the holder when signed in", async () => {
    vi.stubGlobal("fetch", fakeFetch(true, { results: [] }));
    setAccountId("acct-1a2b");
    const adapter = new HttpAdapter(BASE);
    await adapter.search({ query: "hi" } as never);

    const h = headersOf(captured[0].init);
    expect(h["X-Account-Id"]).toBe("acct-1a2b");
    // Content-Type + base URL preserved.
    expect(h["Content-Type"]).toBe("application/json");
    expect(captured[0].url).toBe(`${BASE}/api/search`);
  });

  it("GET carries X-Account-Id equal to the holder when signed in", async () => {
    vi.stubGlobal("fetch", fakeFetch(true, []));
    setAccountId("acct-cafe");
    const adapter = new HttpAdapter(BASE);
    await adapter.listLibrary();

    const h = headersOf(captured[0].init);
    expect(h["X-Account-Id"]).toBe("acct-cafe");
    expect(captured[0].url).toBe(`${BASE}/api/library`);
  });

  it("omits X-Account-Id entirely when the holder is null (signed out)", async () => {
    vi.stubGlobal("fetch", fakeFetch(true, []));
    clearAccountId();
    const adapter = new HttpAdapter(BASE);
    await adapter.search({ query: "hi" } as never);
    await adapter.listLibrary();

    for (const c of captured) {
      expect(headersOf(c.init)["X-Account-Id"]).toBeUndefined();
    }
    // Content-Type still present on POST.
    expect(headersOf(captured[0].init)["Content-Type"]).toBe("application/json");
  });

  it("logout (clear) removes the header from subsequent requests", async () => {
    vi.stubGlobal("fetch", fakeFetch(true, []));
    const adapter = new HttpAdapter(BASE);

    setAccountId("acct-1a2b");
    await adapter.listLibrary();
    expect(headersOf(captured[0].init)["X-Account-Id"]).toBe("acct-1a2b");

    clearAccountId();
    await adapter.listLibrary();
    expect(headersOf(captured[1].init)["X-Account-Id"]).toBeUndefined();
  });

  it("switching account A -> B sends B's id, not A's", async () => {
    vi.stubGlobal("fetch", fakeFetch(true, []));
    const adapter = new HttpAdapter(BASE);

    setAccountId("acct-aaaa");
    await adapter.listLibrary();
    setAccountId("acct-bbbb"); // login as a different account overwrites the holder
    await adapter.listLibrary();

    expect(headersOf(captured[0].init)["X-Account-Id"]).toBe("acct-aaaa");
    expect(headersOf(captured[1].init)["X-Account-Id"]).toBe("acct-bbbb");
  });

  // Property 2 (fast-check): for any valid acct-<hex> id, every user-owned call
  // issued while signed in carries exactly that id.
  it("property: every signed-in request carries the exact holder id", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.hexaString({ minLength: 1, maxLength: 12 }).map((h) => `acct-${h}`),
        async (id) => {
          captured = [];
          vi.stubGlobal("fetch", fakeFetch(true, []));
          setAccountId(id);
          const adapter = new HttpAdapter(BASE);
          await adapter.listLibrary();
          return headersOf(captured[0].init)["X-Account-Id"] === id;
        },
      ),
      { numRuns: 100 },
    );
  });
});
