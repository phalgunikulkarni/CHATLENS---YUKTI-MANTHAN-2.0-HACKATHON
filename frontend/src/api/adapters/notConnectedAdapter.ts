import type { ApiService } from "../ApiService";
import { NotConnectedError } from "../errors";
import type {
  ExplanationSignal,
  ImageStatus,
  RefineRequest,
  RoadmapRequest,
  RoadmapResponse,
  ScheduleConfirmRequest,
  ScheduleProposal,
  ScheduleProposeRequest,
  SearchRequest,
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
  async summarize(_req: SummarizeRequest): Promise<SummaryResponse> { this.fail(); }
  async roadmap(_req: RoadmapRequest): Promise<RoadmapResponse> { this.fail(); }
  async proposeSchedule(_req: ScheduleProposeRequest): Promise<ScheduleProposal> { this.fail(); }
  async confirmSchedule(_req: ScheduleConfirmRequest): Promise<{ confirmed: boolean }> { this.fail(); }
  async uploadImage(_file: File): Promise<ImageStatus> { this.fail(); }
  async getImageStatus(_imageId: string): Promise<ImageStatus> { this.fail(); }
}