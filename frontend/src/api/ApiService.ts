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
  summarize(req: SummarizeRequest): Promise<SummaryResponse>;
  roadmap(req: RoadmapRequest): Promise<RoadmapResponse>;
  proposeSchedule(req: ScheduleProposeRequest): Promise<ScheduleProposal>;
  confirmSchedule(req: ScheduleConfirmRequest): Promise<{ confirmed: boolean }>;
  uploadImage(file: File): Promise<ImageStatus>;
  getImageStatus(imageId: string): Promise<ImageStatus>;
}
