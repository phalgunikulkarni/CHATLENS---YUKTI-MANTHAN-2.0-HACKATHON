import { describe, it, expect } from "vitest";
import { MockAdapter } from "../api/adapters/mockAdapter";

describe("MockAdapter (synthetic demo data)", () => {
  const adapter = new MockAdapter({ latencyMs: 0 });

  it("returns results for the OSI query", async () => {
    const turn = await adapter.search({ query: "Find my CN notes about OSI" });
    expect(turn.intent).toBe("search");
    expect(turn.results && turn.results.length).toBeGreaterThan(0);
  });

  it("returns zero results for an empty: query", async () => {
    const turn = await adapter.search({ query: "empty: nothing here" });
    expect(turn.results).toEqual([]);
  });

  it("refinement adds a handwritten clue and keeps results", async () => {
    const turn = await adapter.refine({ message: "No, they were handwritten", sessionId: "s", activeClues: [] });
    expect(turn.intent).toBe("refinement");
    expect(turn.clues?.some((c) => /handwritten/i.test(c.label))).toBe(true);
  });

  it("failAll injects failures for error-state testing", async () => {
    const failing = new MockAdapter({ failAll: true });
    await expect(failing.search({ query: "x" })).rejects.toThrow();
  });
});
