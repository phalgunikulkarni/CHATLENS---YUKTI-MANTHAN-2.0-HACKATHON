import { ENDPOINTS } from "../contract";
import { getAccountId } from "../accountContext";
import type { ApiService } from "../ApiService";
import type {
  AccessGrantResult,
  AccessStatus,
  ConversationDetail,
  ConversationSummary,
  ExplanationSignal,
  ImageQaRequest,
  ImageQaResponse,
  RefineRequest,
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
 * Live adapter targeting the PROPOSED contract. Only used when
 * VITE_API_BASE_URL is configured. Every method is a thin fetch wrapper.
 */
export class HttpAdapter implements ApiService {
  constructor(private readonly baseUrl: string) {}

  /**
   * Single seam for attaching the account identity to outbound requests. When
   * an account is signed in, the `X-Account-Id` header carrying its
   * `stableAccountId` is added to the existing headers; when signed out no
   * header is added. Preserves all other header behavior (e.g. Content-Type).
   */
  private withAccount(headers: Record<string, string>): Record<string, string> {
    const id = getAccountId();
    return id ? { ...headers, "X-Account-Id": id } : headers;
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: this.withAccount({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return (await res.json()) as T;
  }

  private async get<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      headers: this.withAccount({}),
    });
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return (await res.json()) as T;
  }

  private async patch<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "PATCH",
      headers: this.withAccount({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return (await res.json()) as T;
  }

  private async del(path: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "DELETE",
      headers: this.withAccount({}),
    });
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  }

  private absolutizeResults(turn: TurnResponse): TurnResponse {
    if (!turn.results) return turn;
    return {
      ...turn,
      results: turn.results.map((r) => ({
        ...r,
        thumbnailUrl: this.absolutize(r.thumbnailUrl) ?? r.thumbnailUrl,
        fullUrl: this.absolutize(r.fullUrl),
      })),
    };
  }

  async search(req: SearchRequest): Promise<TurnResponse> {
    const turn = await this.post<TurnResponse>(ENDPOINTS.search, req);
    return this.absolutizeResults(turn);
  }
  async refine(req: RefineRequest): Promise<TurnResponse> {
    const turn = await this.post<TurnResponse>(ENDPOINTS.refine, req);
    return this.absolutizeResults(turn);
  }
  getExplanation(imageId: string) {
    return this.get<ExplanationSignal[]>(ENDPOINTS.explanation(imageId));
  }
  askAboutImage(req: ImageQaRequest) {
    return this.post<ImageQaResponse>(ENDPOINTS.imageQa, req);
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
  grantAccess() {
    return this.post<AccessGrantResult>(ENDPOINTS.accessGrant, {});
  }
  getAccessStatus() {
    return this.get<AccessStatus>(ENDPOINTS.accessStatus);
  }

  /**
   * The backend returns RELATIVE image URLs (e.g. "/api/images/{id}/file").
   * The browser needs them absolute against this adapter's baseUrl. This
   * resolution is scoped to listLibrary only.
   */
  private absolutize(url: string | undefined): string | undefined {
    if (!url) return url;
    return url.startsWith("/") ? `${this.baseUrl}${url}` : url;
  }

  // ---- Account-scoped, backend-durable chat persistence ----
  // All chat calls flow through post/get/patch/del, which attach X-Account-Id
  // via the shared withAccount() seam. ResultRefs carry only image_id + display
  // metadata (no paths/binaries), so no URL absolutization is needed here.
  createChat(title?: string): Promise<ConversationSummary> {
    return this.post<ConversationSummary>(ENDPOINTS.chatsCreate, { title });
  }
  listChats(): Promise<ConversationSummary[]> {
    return this.get<ConversationSummary[]>(ENDPOINTS.chatsList);
  }
  getChat(sessionId: string): Promise<ConversationDetail> {
    return this.get<ConversationDetail>(ENDPOINTS.chat(sessionId));
  }
  deleteChat(sessionId: string): Promise<void> {
    return this.del(ENDPOINTS.chat(sessionId));
  }
  renameChat(sessionId: string, title: string): Promise<ConversationSummary> {
    return this.patch<ConversationSummary>(ENDPOINTS.chat(sessionId), { title });
  }

  async listLibrary(): Promise<SearchResult[]> {
    const items = await this.get<SearchResult[]>(ENDPOINTS.library);
    return items.map((it) => ({
      ...it,
      thumbnailUrl: this.absolutize(it.thumbnailUrl) ?? it.thumbnailUrl,
      fullUrl: this.absolutize(it.fullUrl),
    }));
  }

  async getImageBlob(url: string): Promise<Blob> {
    const res = await fetch(url, { headers: this.withAccount({}) });
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return res.blob();
  }
}
