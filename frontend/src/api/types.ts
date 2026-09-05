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
  /**
   * BLIP-generated natural-language visual description of the image, supplied
   * by the Backend during ingestion. Supplementary context only (never the
   * "Why this result?" explanation). null/undefined/empty -> render nothing.
   */
  visualDescription?: string | null;
  /** Supporting context only - never the sole explanation. */
  matchScore?: number;
  /**
   * Truthful 0-100 similarity derived from real cosine signals (not the fused
   * score). Backend still returns this; it is NO LONGER displayed in the UI
   * (retrieval percentages were removed as a presentation decision).
   */
  similarity?: number;
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

// ---- Local-folder access + indexing ----

/** Result of opening the native folder picker + starting indexing (server-side). */
export interface AccessGrantResult {
  authorized: boolean;
  roots: string[];
  message: string;
}

/** Backend-driven indexing lifecycle for the authorized folders. */
export type IndexingStatus = "idle" | "running" | "ready" | "failed";

/** Authorization + indexing status, polled after a grant. */
export interface AccessStatus {
  authorized: boolean;
  indexing: IndexingStatus;
  roots: string[];
  indexedCount: number;
  error?: string | null;
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

export interface RelatedMemoriesRequest {
  sessionId: string;
  imageId: string;
  query?: string;
}

export interface ResearchRequest {
  sessionId?: string;
  query: string;
  maxResults?: number;
  providers?: string[];
}

export interface ResearchSource {
  title: string | null;
  url: string | null;
  provider: string | null;
  source_type: string | null;
  authors: string[];
  publication_date: string | null;
  year: number | null;
  doi: string | null;
  identifier: string | null;
  abstract: string | null;
  snippet: string | null;
  relevance_score: number | null;
}

export interface ResearchResponse {
  ok: boolean;
  query: string;
  research_answer: string | null;
  key_findings: string[];
  sources: ResearchSource[];
  limitations: string[];
  providers_used: string[];
  providers_failed: string[];
}

export interface BillLineItem {
  name: string;
  price: number;
}

export interface BillFields {
  merchant: string | null;
  date: string | null;
  total: number | null;
  currency: string | null;
  tax: number | null;
  line_items: BillLineItem[];
}

export interface AnalyzeBillRequest {
  sessionId?: string;
  imageIds: string[];
  /** Optional raw OCR text; normally the backend reuses stored OCR by imageId. */
  ocrText?: string;
  /** "analyze" (default) or "split". */
  operation?: "analyze" | "split";
  /** "equal" (default) or "items" when operation === "split". */
  splitMode?: "equal" | "items";
  /** Equal split: number of people. */
  people?: number;
  /** Item split: { personName: [itemIndex, ...] }. */
  assignments?: Record<string, number[]>;
  /** Item split: item indices shared equally among all named people. */
  sharedItems?: number[];
  /** Optional tip amount (backend allocates it; frontend never does). */
  tip?: number;
}

export interface BillRounding {
  rule: string;
  sum?: number;
  reconciles_to_total?: boolean;
  residual_applied_to_last?: number;
}

export interface EqualShare {
  person: string;
  amount: number;
}

export interface ItemShare {
  person: string;
  items_subtotal: number;
  amount: number;
}

export interface BillSplit {
  mode: "equal" | "items";
  currency: string | null;
  total: number | null;
  /** equal mode */
  people_count?: number;
  shares?: EqualShare[];
  /** items mode */
  tax?: number | null;
  tip?: number | null;
  people?: ItemShare[];
  shared_item_indices?: number[];
  rounding: BillRounding;
}

export interface AnalyzeBillResponse {
  ok: boolean;
  message: string;
  fields: BillFields | null;
  confidence: number | null;
  notes: string[];
  /** Present only for a successful split operation. */
  split?: BillSplit | null;
}

export interface SummarizeRequest {
  sessionId: string;
  imageIds: string[];
  mode?: "summary" | "key_points" | "roadmap";
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

// ---- Account-scoped chat persistence (backend-durable) ----
//
// These mirror the backend camelCase DTOs in backend/schemas.py byte-for-byte
// (CreateChat, ConversationSummary, ResultRef, ChatMessage, ConversationDetail).
// The backend is the durable source of truth; the frontend snapshot cache is a
// cache keyed by the canonical `sessionId` these return.

/** Request body for creating a durable conversation. Session id is server-minted. */
export interface CreateChatRequest {
  /** Optional client-supplied title; the session id is always backend-authoritative. */
  title?: string;
}

/** A conversation list/summary row, scoped to the requesting account. */
export interface ConversationSummary {
  sessionId: string;
  title?: string;
  createdAt?: string;
  updatedAt?: string;
}

/** A display-safe reference to a retrieved image (no paths, no binaries). */
export interface ResultRef {
  imageId: string;
  rank: number;
  displayMetadata?: Record<string, unknown>;
}

/** A persisted chat message (user or assistant), ascending by createdAt. */
export interface ChatMessage {
  id: string;
  role: string; // "user" | "assistant"
  content: string;
  createdAt?: string;
  results: ResultRef[];
}

/** Full persisted conversation: messages + result refs + context. */
export interface ConversationDetail {
  sessionId: string;
  title?: string;
  createdAt?: string;
  updatedAt?: string;
  messages: ChatMessage[];
  context?: Record<string, unknown>;
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
