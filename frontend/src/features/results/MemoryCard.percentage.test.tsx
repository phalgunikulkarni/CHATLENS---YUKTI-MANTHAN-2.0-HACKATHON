import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryCard } from "./MemoryCard";
import type { SearchResult } from "../../api/types";

/**
 * Regression: user-facing retrieval percentages were removed (presentation-only
 * decision) while the grounded "Why this result?" affordance is kept.
 *
 * The result below intentionally carries `similarity`, `matchScore`, and per-signal
 * `strength` in the payload (the backend still sends these). This test asserts the
 * card renders NONE of them as a percentage, yet still surfaces the "Why this
 * result?" affordance and the signal TYPE labels (which are labels, not percentages).
 */
const result: SearchResult = {
  id: "mem-osi",
  thumbnailUrl: "data:image/svg+xml,thumb",
  title: "OSI Model - Handwritten Notes",
  description: "Handwritten CN notes with a large layer diagram.",
  category: "note",
  similarity: 97,
  matchScore: 0.97,
  explanation: [
    { type: "ocr", label: 'OCR matched "OSI Model"', icon: "text", strength: 0.95 },
    { type: "visual", label: "Visual match for handwritten notes", icon: "eye", strength: 0.92 },
  ],
};

describe("MemoryCard (no retrieval percentages)", () => {
  it("does not render similarity/match percentages but keeps the why affordance", () => {
    render(
      <MemoryCard
        result={result}
        selected={false}
        view="grid"
        onToggleSelect={() => {}}
        onOpen={() => {}}
        onWhy={() => {}}
        showRetrievalExplanation
      />,
    );

    // No percentage text of any kind should be rendered.
    expect(document.body.textContent ?? "").not.toMatch(/%/);
    expect(screen.queryByText(/Similarity/i)).toBeNull();
    expect(screen.queryByText(/Match/i)).toBeNull();

    // The grounded "Why this result?" affordance stays.
    expect(screen.getByText(/Why this result\?/i)).toBeTruthy();

    // Signal TYPE labels (not percentages) still show.
    expect(screen.getByText("OCR")).toBeTruthy();
    expect(screen.getByText("VISUAL")).toBeTruthy();
  });
});
