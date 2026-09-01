import type { MemoryClue, TurnResponse } from "../api/types";
import type { ConversationState, TurnTranscriptEntry } from "./types";

export const initialConversationState: ConversationState = {
  sessionId: null,
  messages: [],
  activeClues: [],
  turnInProgress: false,
  intentError: false,
  notConnected: false,
};

export type ConversationAction =
  | { type: "SESSION_STARTED"; sessionId: string }
  | { type: "USER_MESSAGE_ADDED"; id: string; text: string }
  | { type: "TURN_STARTED" }
  | { type: "TURN_RECEIVED"; id: string; turn: TurnResponse }
  | { type: "TURN_NOT_CONNECTED"; id: string; message: string }
  | { type: "CLUE_REMOVED"; clueId: string }
  | { type: "SESSION_ENDED" };

/** Append only clues whose id is not already present (dedupe by id, keep order). */
function mergeClues(prior: MemoryClue[], incoming: MemoryClue[] | undefined): MemoryClue[] {
  if (!incoming || incoming.length === 0) return prior;
  const seen = new Set(prior.map((c) => c.id));
  const merged = [...prior];
  for (const c of incoming) {
    if (!seen.has(c.id)) {
      seen.add(c.id);
      merged.push(c);
    }
  }
  return merged;
}

export function conversationReducer(
  state: ConversationState,
  action: ConversationAction
): ConversationState {
  switch (action.type) {
    case "SESSION_STARTED":
      return { ...state, sessionId: action.sessionId };
    case "USER_MESSAGE_ADDED": {
      const entry: TurnTranscriptEntry = { id: action.id, role: "user", text: action.text };
      return { ...state, messages: [...state.messages, entry], notConnected: false };
    }
    case "TURN_STARTED":
      return { ...state, turnInProgress: true, intentError: false, notConnected: false };
    case "TURN_RECEIVED": {
      const { turn } = action;
      const entry: TurnTranscriptEntry = {
        id: action.id,
        role: "agent",
        text: turn.agentMessage,
        intent: turn.intent,
      };
      const messages = [...state.messages, entry];
      const sessionId = turn.sessionId ?? state.sessionId;
      if (turn.intent == null) {
        return { ...state, sessionId, messages, turnInProgress: false, intentError: true };
      }
      if (turn.intent === "refinement") {
        return {
          ...state,
          sessionId,
          messages,
          activeClues: mergeClues(state.activeClues, turn.clues),
          turnInProgress: false,
          intentError: false,
        };
      }
      if (turn.intent === "search") {
        return {
          ...state,
          sessionId,
          messages,
          activeClues: turn.clues ?? [],
          turnInProgress: false,
          intentError: false,
        };
      }
      return { ...state, sessionId, messages, turnInProgress: false, intentError: false };
    }
    case "TURN_NOT_CONNECTED": {
      const entry: TurnTranscriptEntry = { id: action.id, role: "agent", text: action.message };
      return { ...state, messages: [...state.messages, entry], turnInProgress: false, notConnected: true };
    }
    case "CLUE_REMOVED":
      return { ...state, activeClues: state.activeClues.filter((c) => c.id !== action.clueId) };
    case "SESSION_ENDED":
      return { ...initialConversationState };
    default:
      return state;
  }
}