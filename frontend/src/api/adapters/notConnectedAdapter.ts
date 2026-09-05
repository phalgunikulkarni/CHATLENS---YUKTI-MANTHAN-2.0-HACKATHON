import type { ApiService } from "../ApiService";
import { NotConnectedError } from "../errors";
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
} from "../types";

/**
 * The DEFAULT adapter when no backend is configured. Every call rejects with a
 * NotConnectedError so the UI shows an honest "backend not connected" state and
 * NEVER displays fabricated results, explanations, summaries, or statuses.
 */
export class NotConnectedAdapter implements ApiService {
  private fail(): never {
    throw new NotConnectedError();
  }
  async search(_req: SearchRequest): Promise<TurnResponse> { this.fail(); }
  async refine(_req: RefineRequest): Promise<TurnResponse> { this.fail(); }
  async getExplanation(_imageId: string): Promise<ExplanationSignal[]> { this.fail(); }
  async askAboutImage(_req: ImageQaRequest): Promise<ImageQaResponse> { this.fail(); }
  async summarize(_req: SummarizeRequest): Promise<SummaryResponse> { this.fail(); }
  async relatedMemories(_req: RelatedMemoriesRequest): Promise<SearchResult[]> { this.fail(); }
  async roadmap(_req: RoadmapRequest): Promise<RoadmapResponse> { this.fail(); }
  async proposeSchedule(_req: ScheduleProposeRequest): Promise<ScheduleProposal> { this.fail(); }
  async confirmSchedule(_req: ScheduleConfirmRequest): Promise<{ confirmed: boolean }> { this.fail(); }
  async createChat(_title?: string): Promise<ConversationSummary> { this.fail(); }
  async listChats(): Promise<ConversationSummary[]> { this.fail(); }
  async getChat(_sessionId: string): Promise<ConversationDetail> { this.fail(); }
  async deleteChat(_sessionId: string): Promise<void> { this.fail(); }
  async renameChat(_sessionId: string, _title: string): Promise<ConversationSummary> { this.fail(); }
  async listLibrary(): Promise<SearchResult[]> { this.fail(); }
  async grantAccess(): Promise<AccessGrantResult> { this.fail(); }
  async getAccessStatus(): Promise<AccessStatus> { this.fail(); }
}