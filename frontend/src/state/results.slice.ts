import type { SearchResult } from "../api/types";
import type { ResultsState } from "./types";

export const initialResultsState: ResultsState = {
  items: [],
  echoedQuery: "",
  selectedIds: [],
  loading: false,
  refining: false,
  error: null,
  notConnected: false,
  hasSearched: false,
};

export type ResultsAction =
  | { type: "SEARCH_STARTED"; query: string }
  | { type: "REFINE_STARTED" }
  | { type: "RESULTS_REPLACED"; items: SearchResult[]; query: string }
  | { type: "RESULTS_MERGED"; items: SearchResult[] }
  | { type: "RESULT_SELECTION_TOGGLED"; id: string }
  | { type: "SELECTION_CLEARED" }
  | { type: "RETRIEVAL_FAILED"; message: string }
  | { type: "RETRIEVAL_NOT_CONNECTED" }
  | { type: "SESSION_ENDED" };

export function resultsReducer(state: ResultsState, action: ResultsAction): ResultsState {
  switch (action.type) {
    case "SEARCH_STARTED":
      return { ...state, loading: true, refining: false, error: null, notConnected: false, echoedQuery: action.query, hasSearched: true };
    case "REFINE_STARTED":
      return { ...state, refining: true, error: null, notConnected: false };
    case "RESULTS_REPLACED":
      return {
        ...state,
        items: action.items,
        echoedQuery: action.query,
        selectedIds: [],
        loading: false,
        refining: false,
        error: null,
        notConnected: false,
        hasSearched: true,
      };
    case "RESULTS_MERGED":
      return { ...state, items: action.items, loading: false, refining: false, error: null, notConnected: false };
    case "RESULT_SELECTION_TOGGLED": {
      const selected = state.selectedIds.includes(action.id)
        ? state.selectedIds.filter((i) => i !== action.id)
        : [...state.selectedIds, action.id];
      return { ...state, selectedIds: selected };
    }
    case "SELECTION_CLEARED":
      return { ...state, selectedIds: [] };
    case "RETRIEVAL_FAILED":
      return { ...state, loading: false, refining: false, error: action.message, notConnected: false };
    case "RETRIEVAL_NOT_CONNECTED":
      return { ...state, loading: false, refining: false, error: null, notConnected: true, items: [] };
    case "SESSION_ENDED":
      return { ...initialResultsState };
    default:
      return state;
  }
}