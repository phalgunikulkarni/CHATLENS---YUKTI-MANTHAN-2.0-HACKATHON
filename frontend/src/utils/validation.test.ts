import { describe, it, expect } from "vitest";
import fc from "fast-check";
import { isBlank, isSendable } from "../utils/validation";

// Feature: chatlens-frontend, Property 1: A query is sendable iff it contains at least one non-whitespace character; whitespace-only strings never produce a request.
describe("Property 1: query sendability tracks non-whitespace content", () => {
  it("whitespace-only strings are never sendable", () => {
    const ws = fc.stringOf(fc.constantFrom(" ", "\t", "\n", "\r", "\u00a0", "\u2003"), { maxLength: 20 });
    fc.assert(
      fc.property(ws, (s) => {
        expect(isBlank(s)).toBe(true);
        expect(isSendable(s)).toBe(false);
      }),
      { numRuns: 150 }
    );
  });

  it("any string containing a non-whitespace char is sendable", () => {
    fc.assert(
      fc.property(fc.string(), (s) => {
        const hasNonWs = /\S/u.test(s);
        expect(isSendable(s)).toBe(hasNonWs);
      }),
      { numRuns: 200 }
    );
  });
});
