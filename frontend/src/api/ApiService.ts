import type {
  AccessGrantResult,
  AccessStatus,
  ConversationDetail,
  ConversationSummary,
  ExplanationSignal,
  ImageQaRequest,
  ImageQaResponse,
  RefineRequest,
  RelatedMemoriesRequest,
  RoadmapRequest,
  RoadmapResponse,
  ScheduleConfirmRequest,
  ScheduleProposal,
  ScheduleProposeRequest,
  SearchRequest,
  SearchResult,
  SummarizeRequest,
  SummaryResponse,
  TurnResponse,
} from "./types";

/**
 * The single typed boundary between the Frontend and the Backend.
 * No Frontend module other than the adapters that implement this interface may
 * issue network I/O. The concrete adapter (HTTP vs mock) is selected in client.ts.
 */
export interface ApiService {
  search(req: SearchRequest): Promise<TurnResponse>;
  refine(req: RefineRequest): Promise<TurnResponse>;
  getExplanation(imageId: string): Promise<ExplanationSignal[]>;
  /** Conversational Q&A about a specific retrieved image (LLM-backed). */
  askAboutImage(req: ImageQaRequest): Promise<ImageQaResponse>;
  summarize(req: SummarizeRequest): Promise<SummaryResponse>;
  /** Related memories for a selected image (existing retrieval; no new agent). */
  relatedMemories(req: RelatedMemoriesRequest): Promise<SearchResult[]>;
  roadmap(req: RoadmapRequest): Promise<RoadmapResponse>;
  proposeSchedule(req: ScheduleProposeRequest): Promise<ScheduleProposal>;
  confirmSchedule(req: ScheduleConfirmRequest): Promise<{ confirmed: boolean }>;
  // ---- Account-scoped, backend-durable chat persistence ----
  /** Create a durable conversation; returns the canonical backend session id + summary. */
  createChat(title?: string): Promise<ConversationSummary>;
  /** List the signed-in account's durable conversations (account-scoped). */
  listChats(): Promise<ConversationSummary[]>;
  /** Fetch a single conversation's messages + result refs + context. */
  getChat(sessionId: string): Promise<ConversationDetail>;
  /** Delete an owned conversation. */
  deleteChat(sessionId: string): Promise<void>;
  /** Rename/title an owned conversation; returns the updated summary. */
  renameChat(sessionId: string, title: string): Promise<ConversationSummary>;
  /** Read-only list of the user's canonical indexed memories (ML/Chroma). */
  listLibrary(): Promise<SearchResult[]>;
  /** Open the native local folder picker (server-side) and start indexing. */
  grantAccess(): Promise<AccessGrantResult>;
  /** Poll authorization + indexing status. */
  getAccessStatus(): Promise<AccessStatus>;
}