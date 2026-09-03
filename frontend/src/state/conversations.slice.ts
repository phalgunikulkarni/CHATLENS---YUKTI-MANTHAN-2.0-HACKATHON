import type { ActionsState, ConversationState, ResultsState } from "./types";

export interface ConversationSummary {
  id: string;
  title: string; // deterministic; "" until the first query titles it
  createdAt: number;
}

/** A saved snapshot of the three live slices for one conversation. */
export interface ConversationSnapshot {
  conversation: ConversationState;
  results: ResultsState;
  actions: ActionsState;
}

export interface ConversationsState {
  summaries: ConversationSummary[]; // newest first
  activeId: string | null;
  snapshots: Record<string, ConversationSnapshot>;
}

export const initialConversationsState: ConversationsState = {
  summaries: [],
  activeId: null,
  snapshots: {},
};

/** Deterministic conversation title from the first user query. No LLM. */
export function makeTitle(query: string): string {
  const t = query.trim().replace(/\s+/g, " ");
  if (!t) return "New chat";
  return t.length > 40 ? t.slice(0, 40).trimEnd() + "…" : t;
}

export type ConversationsAction =
  | { type: "CONVERSATION_NEW"; id: string; createdAt: number }
  | { type: "CONVERSATION_SELECTED"; id: string }
  | { type: "CONVERSATION_TITLED"; id: string; title: string };

/**
 * The real switch/swap logic lives in the root reducer because changing the
 * active conversation must atomically swap conversation + results + actions.
 * This no-op keeps the store composition pattern consistent.
 */
export function conversationsReducer(
  state: ConversationsState,
  _action: ConversationsAction
): ConversationsState {
  return state;
}
