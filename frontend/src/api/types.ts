/**
 * Typed request/response models for the ChatLens Backend contract.
 *
 * These interfaces make the PROPOSED API contract explicit and encode the
 * data-integrity rule from AGENTS.md and docs/decisions.md ("No Fake Personal
 * History"): optional fields (`?`) are `undefined` when the Backend omits them,
 * and the corresponding UI is omitted rather than fabricated.
 *
 * This module contains types only. It performs no I/O.
 */

export type ExplanationSignalType =
  | "ocr"
  | "semantic"
  | "visual"
  | "metadata"
  | "clue";

/** A single piece of retrieval evidence supplied by the Backend. */
export interface ExplanationSignal {
  type: ExplanationSignalType;
  /** Backend-provided human text, e.g. `OCR matched "OSI Model"`. */
  label: string;
  /** Icon key resolved to an icon component; always paired with text. */
  icon: string;
  /** Optional 0..1 strength for a signal bar; supporting context only. */
  strength?: number;
}

export type MemoryCategory =
  | "screenshot"
  | "note"
  | "code"
  | "receipt"
  | "document"
  | "slide"
  | "other";

/**
 * One image returned by the Backend. Only `id` and `thumbnailUrl` are guaranteed;
 * every other field is optional and rendered only when present.
 */
export interface SearchResult {
  id: string;
  thumbnailUrl: string;
  fullUrl?: string;
  title?: string;
  description?: string;
  category?: MemoryCategory;
  ocrSnippet?: string;
  /** Supporting context only - never the sole explanation. */
  matchScore?: number;
  /** Source or type tag. */
  sourceTag?: string;
  /** Where the memory came from, when the Backend reports it. */
  memorySource?: ConnectorMemorySource;
  /** ISO timestamp, only when the Backend actually has it. */
  capturedAt?: string;
  /** Only the keys the Backend supplies. */
  metadata?: Record<string, string>;
  /** May be embedded here or fetched separately via getExplanation(). */
  explanation?: ExplanationSignal[];
}

/** Backend-provided directive for how the Frontend should render an agent turn. */
export type ResolvedIntent =
  | "search"
  | "refinement"
  | "explanation"
  | "summarize"
  | "roadmap"
  | "schedule";

/** A detail the user remembers, applied as an additional retrieval signal. */
export interface MemoryClue {
  id: string;
  label: string;
}

/** A single agent turn returned by search/refine. */
export interface TurnResponse {
  sessionId: string;
  /** Resolved_Intent; when absent the Frontend shows an error fallback. */
  intent?: ResolvedIntent;
  agentMessage: string;
  clues?: MemoryClue[];
  results?: SearchResult[];
}

export interface SummaryResponse {
  sessionId: string;
  summary: string;
  points?: string[];
  usedImageIds: string[];
}

export interface RoadmapStep {
  order: number;
  title: string;
  detail?: string;
  sourceImageIds?: string[];
}

export interface RoadmapResponse {
  sessionId: string;
  title?: string;
  steps: RoadmapStep[];
}

export interface ProposedEvent {
  title: string;
  start: string;
  end?: string;
  notes?: string;
}

export interface ScheduleProposal {
  sessionId: string;
  events: ProposedEvent[];
}

export type ProcessingStatus =
  | "uploaded"
  | "processing"
  | "indexed"
  | "ready"
  | "failed";

export interface ImageStatus {
  imageId: string;
  status: ProcessingStatus;
}

// ---- Request models ----

export interface SearchRequest {
  query: string;
  sessionId?: string;
}

export interface RefineRequest {
  message: string;
  sessionId: string;
  activeClues: MemoryClue[];
}

export interface SummarizeRequest {
  sessionId: string;
  imageIds: string[];
}

export interface RoadmapRequest {
  sessionId: string;
  imageIds: string[];
}

export interface ScheduleProposeRequest {
  sessionId: string;
  roadmap: RoadmapStep[];
}

export interface ScheduleConfirmRequest {
  sessionId: string;
  events: ProposedEvent[];
}

// ---- Connectors / external memory sources ----

/** Supported external memory sources plus first-party upload. */
export type ConnectorType =
  | "whatsapp"
  | "telegram"
  | "google_drive"
  | "google_photos";

/** Where a memory originated. "uploaded" = added directly in ChatLens. */
export type ConnectorMemorySource = ConnectorType | "uploaded";

/** High-level connection status for a connector. */
export type ConnectorStatus =
  | "not_connected"
  | "connecting"
  | "connected"
  | "error";

/** Fine-grained sync status, only meaningful once connected. */
export type ConnectorSyncStatus =
  | "idle"
  | "syncing"
  | "synced"
  | "paused"
  | "error";

/**
 * Connector state. Everything except `type` is backend-driven. The Frontend
 * never fabricates connected status, sync counts, or timestamps - those appear
 * only when the backend actually reports them.
 */
export interface Connector {
  type: ConnectorType;
  status: ConnectorStatus;
  syncStatus?: ConnectorSyncStatus;
  /** ISO timestamp of the last successful sync, when the backend reports it. */
  lastSyncedAt?: string;
  /** Number of memories indexed from this source, when reported. */
  indexedCount?: number;
  /** 0..100 sync progress, when a sync is in flight and reported. */
  syncProgress?: number;
  /** Human-readable error, when status/syncStatus is "error". */
  error?: string;
}

/**
 * Result of initiating a connection. The backend may return an OAuth/auth URL to
 * redirect the user to. The Frontend does NOT invent auth URLs or fake success.
 */
export interface ConnectorConnectResult {
  type: ConnectorType;
  status: ConnectorStatus;
  /** Auth URL to open, if the backend uses a redirect-based flow. */
  authUrl?: string;
}

// ---- Conversational image Q&A ----

export interface ImageQaRequest {
  imageId: string;
  question: string;
  /** Prior turns for this image, so the backend can keep context. */
  history?: { role: "user" | "assistant"; text: string }[];
}

export interface ImageQaResponse {
  imageId: string;
  answer: string;
}
