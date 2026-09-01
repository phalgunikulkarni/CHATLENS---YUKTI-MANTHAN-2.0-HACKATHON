import { describe, it, expect } from "vitest";
import fc from "fast-check";
import { deriveAltText, ALT_FALLBACK } from "../utils/altText";

// Feature: chatlens-frontend, Property 17: Alt text is derived from Backend text when available and equals a fixed non-fabricated fallback otherwise; never empty.
describe("Property 17: alt text derivation", () => {
  it("is non-empty and uses the fixed fallback only when no text is present", () => {
    const optText = fc.option(fc.string(), { nil: undefined });
    fc.assert(
      fc.property(optText, optText, optText, (title, ocr, source) => {
        const alt = deriveAltText({ title, ocrSnippet: ocr, sourceTag: source });
        expect(alt.length).toBeGreaterThan(0);
        const anyText = [title, ocr, source].some((v) => typeof v === "string" && v.trim().length > 0);
        if (!anyText) {
          expect(alt).toBe(ALT_FALLBACK);
        }
      }),
      { numRuns: 200 }
    );
  });
});
