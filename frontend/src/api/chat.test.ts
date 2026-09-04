import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HttpAdapter } from "./adapters/httpAdapter";
import { clearAccountId, setAccountId } from "./accountContext";

/**
 * Feature: account-scoped-chat-and-isolation (Phase C, task 3.4).
 * The durable chat adapter methods (createChat/listChats/getChat/renameChat/
 * deleteChat) must hit the correct /api/chats routes with the correct HTTP
 * method AND carry the signed-in X-Account-Id header (via the shared
 * withAccount() seam). Validates: Requirements R1.1, R6.1.
 *
 * A fake `fetch` captures the outbound method + url + headers.
 */

const BASE = "http://api.test";

type Captured = { url: string; init?: RequestInit };
let captured: Captured[] = [];

function fakeFetch(body: unknown = {}) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    captured.push({ url, init });
    return {
      ok: true,
      status: 200,
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

describe("HttpAdapter chat methods — routes + account header", () => {
  it("createChat POSTs to /api/chats with the account header and title body", async () => {
    vi.stubGlobal("fetch", fakeFetch({ sessionId: "s1", title: "T", createdAt: null, updatedAt: null }));
    setAccountId("acct-1a2b");
    const adapter = new HttpAdapter(BASE);

    const summary = await adapter.createChat("My chat");

    const c = captured[0];
    expect(c.url).toBe(`${BASE}/api/chats`);
    expect(c.init?.method).toBe("POST");
    expect(headersOf(c.init)["X-Account-Id"]).toBe("acct-1a2b");
    expect(headersOf(c.init)["Content-Type"]).toBe("application/json");
    expect(JSON.parse(String(c.init?.body))).toEqual({ title: "My chat" });
    expect(summary.sessionId).toBe("s1");
  });

  it("listChats GETs /api/chats with the account header", async () => {
    vi.stubGlobal("fetch", fakeFetch([]));
    setAccountId("acct-cafe");
    const adapter = new HttpAdapter(BASE);

    await adapter.listChats();

    const c = captured[0];
    expect(c.url).toBe(`${BASE}/api/chats`);
    // GET has no explicit method set on the fetch init (default GET).
    expect(c.init?.method).toBeUndefined();
    expect(headersOf(c.init)["X-Account-Id"]).toBe("acct-cafe");
  });

  it("getChat GETs /api/chats/{id} with the account header", async () => {
    vi.stubGlobal("fetch", fakeFetch({ sessionId: "s9", messages: [] }));
    setAccountId("acct-99");
    const adapter = new HttpAdapter(BASE);

    await adapter.getChat("s9");

    const c = captured[0];
    expect(c.url).toBe(`${BASE}/api/chats/s9`);
    expect(headersOf(c.init)["X-Account-Id"]).toBe("acct-99");
  });

  it("renameChat PATCHes /api/chats/{id} with title body + account header", async () => {
    vi.stubGlobal("fetch", fakeFetch({ sessionId: "s2", title: "New" }));
    setAccountId("acct-abcd");
    const adapter = new HttpAdapter(BASE);

    await adapter.renameChat("s2", "New");

    const c = captured[0];
    expect(c.url).toBe(`${BASE}/api/chats/s2`);
    expect(c.init?.method).toBe("PATCH");
    expect(headersOf(c.init)["X-Account-Id"]).toBe("acct-abcd");
    expect(JSON.parse(String(c.init?.body))).toEqual({ title: "New" });
  });

  it("deleteChat DELETEs /api/chats/{id} with the account header", async () => {
    vi.stubGlobal("fetch", fakeFetch({ deleted: "s3" }));
    setAccountId("acct-dead");
    const adapter = new HttpAdapter(BASE);

    await adapter.deleteChat("s3");

    const c = captured[0];
    expect(c.url).toBe(`${BASE}/api/chats/s3`);
    expect(c.init?.method).toBe("DELETE");
    expect(headersOf(c.init)["X-Account-Id"]).toBe("acct-dead");
  });

  it("omits X-Account-Id on chat calls when signed out", async () => {
    vi.stubGlobal("fetch", fakeFetch([]));
    clearAccountId();
    const adapter = new HttpAdapter(BASE);

    await adapter.listChats();
    await adapter.createChat();

    for (const c of captured) {
      expect(headersOf(c.init)["X-Account-Id"]).toBeUndefined();
    }
  });
});
