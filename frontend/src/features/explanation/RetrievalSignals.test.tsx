import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RetrievalSignals } from "./RetrievalSignals";
import type { ExplanationSignal } from "../../api/types";

/**
 * Regression: the "Why this result?" explanation stays grounded (type chips +
 * expanded label + short type description) but shows NO retrieval percentages.
 * Signals below carry `strength` (backend still sends it); it must never render
 * as a percentage or as a strength bar.
 */
const signals: ExplanationSignal[] = [
  { type: "ocr", label: 'OCR matched "OSI Model"', icon: "text", strength: 0.95 },
  { type: "visual", label: "Visual match for handwritten notes", icon: "eye", strength: 0.92 },
];

describe("RetrievalSignals (grounded, no percentages)", () => {
  it("renders type chips and a grounded explanation without any percentage", async () => {
    const user = userEvent.setup();
    render(<RetrievalSignals signals={signals} />);

    // Type labels are present; no percentage anywhere before expanding.
    expect(screen.getByText("OCR")).toBeTruthy();
    expect(screen.getByText("Visual")).toBeTruthy();
    expect(document.body.textContent ?? "").not.toMatch(/%/);
    expect(screen.queryByText(/Overall relevance/i)).toBeNull();

    // Expanding a chip reveals the grounded label + short type explanation, still no %.
    await user.click(screen.getByText("OCR"));
    expect(screen.getByText('OCR matched "OSI Model"')).toBeTruthy();
    expect(screen.getByText(/Matched text detected inside the image\./i)).toBeTruthy();
    expect(document.body.textContent ?? "").not.toMatch(/%/);
    // No strength bar element.
    expect(document.querySelector(".bar")).toBeNull();
  });

  it("shows the empty state when no signals are present", () => {
    render(<RetrievalSignals signals={undefined} />);
    expect(screen.getByText(/Explanation not available for this result\./i)).toBeTruthy();
  });
});
