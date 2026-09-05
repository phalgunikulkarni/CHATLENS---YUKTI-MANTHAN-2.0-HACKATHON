import { describe, it, expect } from "vitest";
import { MockAdapter } from "./adapters/mockAdapter";

describe("MockAdapter.analyzeBill", () => {
  const adapter = new MockAdapter({ latencyMs: 0 });

  it("returns a structured receipt analysis with fields and items", async () => {
    const res = await adapter.analyzeBill({ imageIds: ["img-1"] });
    expect(res.ok).toBe(true);
    expect(res.fields).not.toBeNull();
    expect(res.fields!.total).toBeTypeOf("number");
    expect(res.fields!.currency).toBeTruthy();
    expect(res.fields!.line_items.length).toBeGreaterThan(0);
  });
});
