import type { SearchHistoryEntry, Toast, UiState, ViewName } from "./types";

const HISTORY_KEY = "chatlens.searchHistory.v1";

/** Load real user search history from localStorage (empty if none/unavailable). */
function loadHistory(): SearchHistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as SearchHistoryEntry[]) : [];
  } catch {
    return [];
  }
}

function persistHistory(entries: SearchHistoryEntry[]): void {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(entries));
  } catch {
    // Ignore storage failures; history is a convenience, not a source of truth.
  }
}

export const initialUiState: UiState = {
  view: "search",
  drawerOpenForId: null,
  confirmDialogOpen: false,
  offline: false,
  toasts: [],
  searchHistory: loadHistory(),
};

export type UiAction =
  | { type: "VIEW_CHANGED"; view: ViewName }
  | { type: "DRAWER_OPENED"; id: string }
  | { type: "DRAWER_CLOSED" }
  | { type: "CONFIRM_DIALOG_OPENED" }
  | { type: "CONFIRM_DIALOG_CLOSED" }
  | { type: "OFFLINE_CHANGED"; offline: boolean }
  | { type: "TOAST_ADDED"; toast: Toast }
  | { type: "TOAST_DISMISSED"; id: string }
  | { type: "SEARCH_RECORDED"; entry: SearchHistoryEntry }
  | { type: "HISTORY_CLEARED" }
  | { type: "HISTORY_ITEM_REMOVED"; id: string };

export function uiReducer(state: UiState, action: UiAction): UiState {
  switch (action.type) {
    case "VIEW_CHANGED":
      return { ...state, view: action.view };
    case "DRAWER_OPENED":
      return { ...state, drawerOpenForId: action.id };
    case "DRAWER_CLOSED":
      return { ...state, drawerOpenForId: null };
    case "CONFIRM_DIALOG_OPENED":
      return { ...state, confirmDialogOpen: true };
    case "CONFIRM_DIALOG_CLOSED":
      return { ...state, confirmDialogOpen: false };
    case "OFFLINE_CHANGED":
      return { ...state, offline: action.offline };
    case "TOAST_ADDED":
      return { ...state, toasts: [...state.toasts, action.toast] };
    case "TOAST_DISMISSED":
      return { ...state, toasts: state.toasts.filter((t) => t.id !== action.id) };
    case "SEARCH_RECORDED": {
      // Only real user searches reach here. Newest first, de-duplicated by query.
      const withoutDupe = state.searchHistory.filter(
        (e) => e.query.trim().toLowerCase() !== action.entry.query.trim().toLowerCase()
      );
      const next = [action.entry, ...withoutDupe].slice(0, 25);
      persistHistory(next);
      return { ...state, searchHistory: next };
    }
    case "HISTORY_CLEARED":
      persistHistory([]);
      return { ...state, searchHistory: [] };
    case "HISTORY_ITEM_REMOVED": {
      const next = state.searchHistory.filter((e) => e.id !== action.id);
      persistHistory(next);
      return { ...state, searchHistory: next };
    }
    default:
      return state;
  }
}