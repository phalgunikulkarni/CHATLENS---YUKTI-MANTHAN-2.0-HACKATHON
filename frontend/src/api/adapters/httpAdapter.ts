import { ENDPOINTS } from "../contract";
import type { ApiService } from "../ApiService";
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
 * Live adapter targeting the PROPOSED contract. Only used when
 * VITE_API_BASE_URL is configured. Every method is a thin fetch wrapper.
 */
export class HttpAdapter implements ApiService {
  constructor(private readonly baseUrl: string) {}

  private async post<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return (await res.json()) as T;
  }

  private async get<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`);
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return (await res.json()) as T;
  }

  search(req: SearchRequest) {
    return this.post<TurnResponse>(ENDPOINTS.search, req);
  }
  refine(req: RefineRequest) {
    return this.post<TurnResponse>(ENDPOINTS.refine, req);
  }
  getExplanation(imageId: string) {
    return this.get<ExplanationSignal[]>(ENDPOINTS.explanation(imageId));
  }
  summarize(req: SummarizeRequest) {
    return this.post<SummaryResponse>(ENDPOINTS.summarize, req);
  }
  roadmap(req: RoadmapRequest) {
    return this.post<RoadmapResponse>(ENDPOINTS.roadmap, req);
  }
  proposeSchedule(req: ScheduleProposeRequest) {
    return this.post<ScheduleProposal>(ENDPOINTS.schedulePropose, req);
  }
  confirmSchedule(req: ScheduleConfirmRequest) {
    return this.post<{ confirmed: boolean }>(ENDPOINTS.scheduleConfirm, req);
  }
  async uploadImage(file: File) {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${this.baseUrl}${ENDPOINTS.images}`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    return (await res.json()) as ImageStatus;
  }
  getImageStatus(imageId: string) {
    return this.get<ImageStatus>(ENDPOINTS.imageStatus(imageId));
  }
}
