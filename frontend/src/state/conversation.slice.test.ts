import { describe, it, expect } from "vitest";
import fc from "fast-check";
import { conversationReducer, initialConversationState } from "../state/conversation.slice";
import type { MemoryClue, TurnResponse } from "../api/types";

const clueArb = fc.record({ id: fc.string({ minLength: 1 }), label: fc.string() });

// Feature: chatlens-frontend, Property 4: Refinement retains prior clues and adds the new clue (dedupe by id) in place.
describe("Property 4: refinement retains prior clues and adds new (dedupe by id)", () => {
  it("result clue set = prior + new, deduped by id, order preserved", () => {
    fc.assert(
      fc.property(fc.array(clueArb), fc.array(clueArb), (prior, incoming) => {
        const dedupPrior: MemoryClue[] = [];
        const seen = new Set<string>();
        for (const c of prior) { if (!seen.has(c.id)) { seen.add(c.id); dedupPrior.push(c); } }
        const start = { ...initialConversationState, sessionId: "s", activeClues: dedupPrior };
        const turn: TurnResponse = { sessionId: "s", intent: "refinement", agentMessage: "", clues: incoming };
        const next = conversationReducer(start, { type: "TURN_RECEIVED", id: "a1", turn });
        const expectedIds = [...dedupPrior.map((c) => c.id)];
        for (const c of incoming) { if (!expectedIds.includes(c.id)) expectedIds.push(c.id); }
        expect(next.activeClues.map((c) => c.id)).toEqual(expectedIds);
      }),
      { numRuns: 150 }
    );
  });
});

// Feature: chatlens-frontend, Property 5: A new search resets clues to the turn's clues (or empty).
describe("Property 5: new search resets the active clue set", () => {
  it("prior clues are replaced by the turn's clues on a search intent", () => {
    fc.assert(
      fc.property(fc.array(clueArb), fc.option(fc.array(clueArb), { nil: undefined }), (prior, incoming) => {
        const start = { ...initialConversationState, sessionId: "s", activeClues: prior };
        const turn: TurnResponse = { sessionId: "s", intent: "search", agentMessage: "", clues: incoming };
        const next = conversationReducer(start, { type: "TURN_RECEIVED", id: "a1", turn });
        expect(next.activeClues).toEqual(incoming ?? []);
      }),
      { numRuns: 150 }
    );
  });
});

// Feature: chatlens-frontend, Property 6: Transcript preserves dispatch order, is discarded on SESSION_ENDED, and is never persisted.
describe("Property 6: transcript order, discard on end, no persistence", () => {
  it("messages appear in dispatch order and clear on SESSION_ENDED without touching storage", () => {
    const writes: string[] = [];
    const origLocal = Storage.prototype.setItem;
    Storage.prototype.setItem = function (k: string, v: string) { writes.push(k); return origLocal.call(this, k, v); };
    try {
      fc.assert(
        fc.property(fc.array(fc.string({ minLength: 1 }), { maxLength: 12 }), (texts) => {
          let state = initialConversationState;
          texts.forEach((t, i) => {
            state = conversationReducer(state, { type: "USER_MESSAGE_ADDED", id: `u${i}`, text: t });
          });
          expect(state.messages.map((m) => m.text)).toEqual(texts);
          const ended = conversationReducer(state, { type: "SESSION_ENDED" });
          expect(ended.messages).toEqual([]);
        }),
        { numRuns: 120 }
      );
      expect(writes).toEqual([]);
    } finally {
      Storage.prototype.setItem = origLocal;
    }
  });
});

// intent-missing path (Req 5.3) as a targeted unit assertion within reducer tests.
describe("Missing intent sets intentError and records the agent message", () => {
  it("keeps clues unchanged and flags intentError", () => {
    const start = { ...initialConversationState, sessionId: "s", activeClues: [{ id: "c", label: "x" }] };
    const turn: TurnResponse = { sessionId: "s", agentMessage: "no intent" };
    const next = conversationReducer(start, { type: "TURN_RECEIVED", id: "a", turn });
    expect(next.intentError).toBe(true);
    expect(next.activeClues).toEqual(start.activeClues);
    expect(next.messages.at(-1)?.text).toBe("no intent");
  });
});
