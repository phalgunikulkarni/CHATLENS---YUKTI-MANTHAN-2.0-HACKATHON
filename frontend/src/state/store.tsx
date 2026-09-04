import { createContext, useReducer, type Dispatch, type ReactNode } from "react";
import { actionsReducer, initialActionsState, type ActionsAction } from "./actions.slice";
import { connectorsReducer, initialConnectorsState, type ConnectorsAction } from "./connectors.slice";
import { conversationReducer, initialConversationState, type ConversationAction } from "./conversation.slice";
import { initialConversationsState, type ConversationsAction } from "./conversations.slice";
import { initialResultsState, resultsReducer, type ResultsAction } from "./results.slice";
import { initialUiState, uiReducer, type UiAction } from "./ui.slice";
import type { RootState } from "./types";

/**
 * Account-lifecycle reset. Dispatched by the auth lifecycle when the signed-in
 * account changes or on logout so no prior-account conversation/results/actions
 * content lingers in the UI. Resets ONLY the account-specific slices
 * (conversation, conversations, results, actions); connectors and ui are left
 * untouched. `STATE_RESET` is an alias with identical semantics.
 */
export type AccountLifecycleAction =
  | { type: "ACCOUNT_CHANGED" }
  | { type: "STATE_RESET" };

export type AppAction =
  | ConversationAction
  | ResultsAction
  | ActionsAction
  | ConnectorsAction
  | ConversationsAction
  | UiAction
  | AccountLifecycleAction;

export const initialRootState: RootState = {
  conversation: initialConversationState,
  results: initialResultsState,
  actions: initialActionsState,
  connectors: initialConnectorsState,
  conversations: initialConversationsState,
  ui: initialUiState,
};

export function rootReducer(state: RootState, action: AppAction): RootState {
  // Base pass: run every existing slice reducer as today.
  let next: RootState = {
    conversation: conversationReducer(state.conversation, action as ConversationAction),
    results: resultsReducer(state.results, action as ResultsAction),
    actions: actionsReducer(state.actions, action as ActionsAction),
    connectors: connectorsReducer(state.connectors, action as ConnectorsAction),
    ui: uiReducer(state.ui, action as UiAction),
    conversations: state.conversations,
  };

  switch (action.type) {
    case "ACCOUNT_CHANGED":
    case "STATE_RESET": {
      // Reset only the account-specific slices; leave connectors and ui alone.
      next = {
        ...next,
        conversation: initialConversationState,
        results: initialResultsState,
        actions: initialActionsState,
        conversations: initialConversationsState,
      };
      return next;
    }
    case "CONVERSATION_NEW": {
      const convs = next.conversations;
      // Archive the current live slices under the currently active id (if any).
      const snapshots = { ...convs.snapshots };
      if (convs.activeId) {
        snapshots[convs.activeId] = {
          conversation: state.conversation,
          results: state.results,
          actions: state.actions,
        };
      }
      const summary = { id: action.id, title: "", createdAt: action.createdAt };
      next = {
        ...next,
        conversation: initialConversationState,
        results: initialResultsState,
        actions: initialActionsState,
        conversations: {
          summaries: [summary, ...convs.summaries],
          activeId: action.id,
          snapshots,
        },
      };
      return next;
    }
    case "CONVERSATION_SELECTED": {
      const convs = next.conversations;
      if (action.id === convs.activeId) return next;
      const snapshots = { ...convs.snapshots };
      if (convs.activeId) {
        snapshots[convs.activeId] = {
          conversation: state.conversation,
          results: state.results,
          actions: state.actions,
        };
      }
      const restore = snapshots[action.id];
      next = {
        ...next,
        conversation: restore ? restore.conversation : initialConversationState,
        results: restore ? restore.results : initialResultsState,
        actions: restore ? restore.actions : initialActionsState,
        conversations: { ...convs, activeId: action.id, snapshots },
      };
      return next;
    }
    case "CONVERSATION_TITLED": {
      const convs = next.conversations;
      next = {
        ...next,
        conversations: {
          ...convs,
          summaries: convs.summaries.map((s) =>
            s.id === action.id && !s.title ? { ...s, title: action.title } : s
          ),
        },
      };
      return next;
    }
    case "CONVERSATIONS_LOADED": {
      // Populate the conversation list from backend-durable summaries. The
      // canonical backend sessionId becomes the local summary id so selection
      // and hydration target the same conversation. Backend order (newest
      // first) is preserved. No snapshots are created here; selecting a
      // conversation hydrates its transcript via getChat on demand.
      const summaries = action.summaries.map((s) => ({
        id: s.sessionId,
        title: s.title ?? "",
        createdAt: s.createdAt ? Date.parse(s.createdAt) || 0 : 0,
      }));
      next = {
        ...next,
        conversations: {
          summaries,
          activeId: null,
          snapshots: {},
        },
      };
      return next;
    }
    default:
      return next;
  }
}

export const StateContext = createContext<RootState | null>(null);
export const DispatchContext = createContext<Dispatch<AppAction> | null>(null);

export interface StoreProviderProps {
  children: ReactNode;
  preloadedState?: RootState;
}

export function StoreProvider({ children, preloadedState }: StoreProviderProps) {
  const [state, dispatch] = useReducer(rootReducer, preloadedState ?? initialRootState);
  return (
    <StateContext.Provider value={state}>
      <DispatchContext.Provider value={dispatch}>{children}</DispatchContext.Provider>
    </StateContext.Provider>
  );
}
