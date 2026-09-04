import { describe, expect, it } from "vitest";
import { rootReducer, initialRootState } from "./store";
import { initialConversationState } from "./conversation.slice";
import { initialResultsState } from "./results.slice";
import { initialActionsState } from "./actions.slice";
import { initialConversationsState } from "./conversations.slice";
import type { RootState } from "./types";

/**
 * Feature: account-scoped-chat-and-isolation (Phase A), Task 1.5.
 * ACCOUNT_CHANGED / STATE_RESET reset ONLY the account-specific slices
 * (conversation, conversations, results, actions) and leave connectors + ui
 * untouched. Validates: Requirement R1.4.
 */

function dirtyState(): RootState {
  return {
    ...initialRootState,
    conversation: { ...initialConversationState, sessionId: "session_x", messages: [{ id: "m1", role: "user", text: "hi" }] },
    results: { ...initialResultsState, items: [{ id: "r1" } as never], hasSearched: true, echoedQuery: "cats" },
    actions: { ...initialActionsState, scheduled: true, summary: { sessionId: "s", summary: "x", usedImageIds: [] } as never },
    conversations: { summaries: [{ id: "c1", title: "t", createdAt: 1 }], activeId: "c1", snapshots: {} },
    connectors: { ...initialRootState.connectors },
    ui: { ...initialRootState.ui, view: "library" },
  };
}

describe("store account reset", () => {
  it("ACCOUNT_CHANGED returns the four account slices to initial", () => {
    const next = rootReducer(dirtyState(), { type: "ACCOUNT_CHANGED" });
    expect(next.conversation).toEqual(initialConversationState);
    expect(next.results).toEqual(initialResultsState);
    expect(next.actions).toEqual(initialActionsState);
    expect(next.conversations).toEqual(initialConversationsState);
  });

  it("STATE_RESET behaves identically to ACCOUNT_CHANGED", () => {
    const next = rootReducer(dirtyState(), { type: "STATE_RESET" });
    expect(next.conversation).toEqual(initialConversationState);
    expect(next.results).toEqual(initialResultsState);
    expect(next.actions).toEqual(initialActionsState);
    expect(next.conversations).toEqual(initialConversationsState);
  });

  it("leaves connectors and ui slices untouched", () => {
    const start = dirtyState();
    const next = rootReducer(start, { type: "ACCOUNT_CHANGED" });
    expect(next.connectors).toEqual(start.connectors);
    expect(next.ui).toEqual(start.ui); // e.g. view stays "library"
    expect(next.ui.view).toBe("library");
  });
});
