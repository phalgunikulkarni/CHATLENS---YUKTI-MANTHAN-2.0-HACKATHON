import { describe, it, expect } from "vitest";
import { MockAdapter } from "./adapters/mockAdapter";

describe("MockAdapter.research", () => {
  const adapter = new MockAdapter({ latencyMs: 0 });

  it("returns a structured research response with clickable source URLs", async () => {
    const res = await adapter.research({ query: "transformers" });
    expect(res.ok).toBe(true);
    expect(res.research_answer).toBeTruthy();
    expect(res.key_findings.length).toBeGreaterThan(0);
    expect(res.sources.length).toBeGreaterThan(0);
    // every source URL is a real http(s) link (never fabricated/empty here)
    for (const s of res.sources) {
      expect(s.url && /^https?:\/\//.test(s.url)).toBe(true);
      expect(s.provider).toBeTruthy();
    }
  });
});
