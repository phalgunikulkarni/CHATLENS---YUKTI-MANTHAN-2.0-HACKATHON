import { createContext, useReducer, type Dispatch, type ReactNode } from "react";
import { actionsReducer, initialActionsState, type ActionsAction } from "./actions.slice";
import { connectorsReducer, initialConnectorsState, type ConnectorsAction } from "./connectors.slice";
import { settingsReducer, initialSettingsState, type SettingsAction } from "./settings.slice";
import { conversationReducer, initialConversationState, type ConversationAction } from "./conversation.slice";
import { ingestionReducer, initialIngestionState, type IngestionAction } from "./ingestion.slice";
import { initialResultsState, resultsReducer, type ResultsAction } from "./results.slice";
import { initialUiState, uiReducer, type UiAction } from "./ui.slice";
import type { RootState } from "./types";

export type AppAction =
  | ConversationAction
  | ResultsAction
  | IngestionAction
  | ActionsAction
  | ConnectorsAction
  | SettingsAction
  | UiAction;

export const initialRootState: RootState = {
  conversation: initialConversationState,
  results: initialResultsState,
  ingestion: initialIngestionState,
  actions: initialActionsState,
  connectors: initialConnectorsState,
  settings: initialSettingsState,
  ui: initialUiState,
};

export function rootReducer(state: RootState, action: AppAction): RootState {
  return {
    conversation: conversationReducer(state.conversation, action as ConversationAction),
    results: resultsReducer(state.results, action as ResultsAction),
    ingestion: ingestionReducer(state.ingestion, action as IngestionAction),
    actions: actionsReducer(state.actions, action as ActionsAction),
    connectors: connectorsReducer(state.connectors, action as ConnectorsAction),
    settings: settingsReducer(state.settings, action as SettingsAction),
    ui: uiReducer(state.ui, action as UiAction),
  };
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