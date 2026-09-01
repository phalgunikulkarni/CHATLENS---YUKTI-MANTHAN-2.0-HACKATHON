import type {
  MemoryClue,
  ProcessingStatus,
  RoadmapResponse,
  ScheduleProposal,
  SearchResult,
  SummaryResponse,
  TurnResponse,
} from "../api/types";
import type { ConnectorsState } from "./connectors.slice";
import type { SettingsState } from "./settings.slice";

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

export interface UploadValidation {
  valid: boolean;
  error?: string;
}

export interface UploadItem {
  id: string;
  fileName: string;
  fileSize: number;
  previewUrl: string;
  validation: UploadValidation;
  status: ProcessingStatus;
  /** 0..100 upload/processing progress (client-side upload only). */
  progress: number;
  /** True while awaiting a backend that is not connected. */
  awaitingBackend?: boolean;
  error?: string;
}

export interface IngestionState {
  queue: UploadItem[];
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

export type ViewName = "search" | "library" | "history" | "upload" | "connectors";

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
  /** Images the user uploaded this session (used by the Library until backend). */
  sessionMemoryIds: string[];
  /** Non-intrusive reminder to add images (set when onboarding is skipped). */
  showImageReminder: boolean;
}

export interface RootState {
  conversation: ConversationState;
  connectors: ConnectorsState;
  settings: SettingsState;
  results: ResultsState;
  ingestion: IngestionState;
  actions: ActionsState;
  ui: UiState;
}