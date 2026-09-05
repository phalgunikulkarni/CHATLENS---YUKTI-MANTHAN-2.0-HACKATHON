import type {
  MemoryClue,
  RoadmapResponse,
  ScheduleProposal,
  SearchResult,
  SummaryResponse,
  TurnResponse,
} from "../api/types";
import type { ConnectorsState } from "./connectors.slice";
import type { ConversationsState } from "./conversations.slice";

export interface TurnTranscriptEntry {
  id: string;
  role: "user" | "agent";
  text: string;
  intent?: TurnResponse["intent"];
}

export interface ConversationState {
  sessionId: string | null;
  messages: TurnTranscriptEntry[];
  activeClues: MemoryClue[];
  turnInProgress: boolean;
  intentError: boolean;
  /** True when a turn failed because the backend is not connected. */
  notConnected: boolean;
}

export interface ResultsState {
  items: SearchResult[];
  echoedQuery: string;
  selectedIds: string[];
  loading: boolean;
  refining: boolean;
  error: string | null;
  /** True when the last retrieval failed because no backend is connected. */
  notConnected: boolean;
  hasSearched: boolean;
}

export interface ActionsState {
  summary: SummaryResponse | null;
  roadmap: RoadmapResponse | null;
  proposal: ScheduleProposal | null;
  scheduled: boolean;
  loading: boolean;
  error: string | null;
  /** True when the last action failed because no backend is connected. */
  notConnected: boolean;
}

export type ToastTone = "info" | "success" | "error";
export interface Toast {
  id: string;
  message: string;
  tone: ToastTone;
}

export type ViewName = "search" | "library" | "connectors" | "history";

export interface SearchHistoryEntry {
  id: string;
  query: string;
  at: number;
  resultCount: number;
}

export interface UiState {
  view: ViewName;
  drawerOpenForId: string | null;
  confirmDialogOpen: boolean;
  offline: boolean;
  toasts: Toast[];
  /** Real user searches performed this session (persisted to localStorage). */
  searchHistory: SearchHistoryEntry[];
}

export interface RootState {
  conversation: ConversationState;
  connectors: ConnectorsState;
  conversations: ConversationsState;
  results: ResultsState;
  actions: ActionsState;
  ui: UiState;
}