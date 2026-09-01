import { describe, it, expect } from "vitest";
import fc from "fast-check";
import { validateFile, ACCEPTED_TYPES, MAX_BYTES } from "../state/ingestion.slice";

// Feature: chatlens-frontend, Property 10: Upload validation partitions files - accepted type + size <= max is valid, else invalid with a message.
describe("Property 10: upload validation partitions files correctly", () => {
  it("valid iff accepted type and size within limit", () => {
    const typeArb = fc.constantFrom(...ACCEPTED_TYPES, "application/pdf", "text/plain", "image/tiff");
    const sizeArb = fc.integer({ min: 0, max: MAX_BYTES * 2 });
    fc.assert(
      fc.property(typeArb, sizeArb, (type, size) => {
        const v = validateFile(type, size);
        const expected = ACCEPTED_TYPES.includes(type) && size <= MAX_BYTES;
        expect(v.valid).toBe(expected);
        if (!v.valid) expect(typeof v.error).toBe("string");
      }),
      { numRuns: 200 }
    );
  });
});
