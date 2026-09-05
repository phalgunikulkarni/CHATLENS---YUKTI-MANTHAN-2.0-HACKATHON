import { describe, it, expect, vi, afterEach } from "vitest";
import { HttpAdapter } from "./adapters/httpAdapter";

function mockFetchOnce(status: number, jsonBody: unknown) {
  const fn = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => jsonBody,
  } as Response);
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("HttpAdapter.analyzeBill — 422 error handling (no object leaks to React)", () => {
  const adapter = new HttpAdapter("http://127.0.0.1:8000");

  it("sends sessionId in the request payload (prevents the missing-field 422)", async () => {
    const fetchMock = mockFetchOnce(200, {
      ok: true, message: "ok",
      data: { fields: { merchant: "M", date: null, total: 5, currency: "USD", tax: null, line_items: [] },
              confidence: 1, notes: [], split: null },
    });
    await adapter.analyzeBill({ sessionId: "pending", imageIds: ["img-1"] });
    const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string);
    expect(body.sessionId).toBe("pending");
    expect(body.imageIds).toEqual(["img-1"]);
  });

  it("converts a FastAPI 422 validation array {type,loc,msg,input} into a readable STRING", async () => {
    mockFetchOnce(422, {
      detail: [
        { type: "missing", loc: ["body", "sessionId"], msg: "Field required", input: {} },
      ],
    });
    const res = await adapter.analyzeBill({ imageIds: ["img-1"] });
    expect(res.ok).toBe(false);
    // message + notes must be plain strings — never the raw object/array.
    expect(typeof res.message).toBe("string");
    expect(res.message).toContain("Field required");
    expect(res.notes.every((n) => typeof n === "string")).toBe(true);
    // no object with the crashing keys survived
    expect(JSON.stringify(res)).not.toContain('"loc"');
    expect(JSON.stringify(res)).not.toContain('"input"');
  });

  it("handles a string HTTPException detail", async () => {
    mockFetchOnce(422, { detail: "No readable total on this receipt." });
    const res = await adapter.analyzeBill({ sessionId: "pending", imageIds: ["img-1"] });
    expect(res.ok).toBe(false);
    expect(res.message).toBe("No readable total on this receipt.");
  });

  it("falls back to a readable message for an unexpected body shape", async () => {
    mockFetchOnce(500, { unexpected: { nested: true } });
    const res = await adapter.analyzeBill({ sessionId: "pending", imageIds: ["img-1"] });
    expect(typeof res.message).toBe("string");
    expect(res.message).toContain("Could not analyze bill");
  });
});
