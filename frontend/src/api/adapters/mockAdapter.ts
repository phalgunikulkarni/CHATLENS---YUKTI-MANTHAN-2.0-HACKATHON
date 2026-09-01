import type { ApiService } from "../ApiService";
import type {
  ExplanationSignal,
  ImageStatus,
  MemoryClue,
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
import { MOCK_MEMORIES } from "../../data/mockMemories";

/**
 * SYNTHETIC DEV/DEMO DATA - NOT genuine user history.
 *
 * Every value produced by this adapter is curated and clearly synthetic per
 * AGENTS.md. It exists so the Frontend can be built, demoed, and tested with no
 * live Backend. It fabricates nothing about real users. The demo dataset lives
 * in src/data/mockMemories.ts and is isolated from production API code so it can
 * be swapped for real Backend responses.
 */

export interface MockAdapterOptions {
  latencyMs?: number;
  failAll?: boolean;
}

const clue = (id: string, label: string): MemoryClue => ({ id, label });

function byId(id: string): SearchResult | undefined {
  return MOCK_MEMORIES.find((m) => m.id === id);
}

function pick(ids: string[]): SearchResult[] {
  return ids.map(byId).filter((r): r is SearchResult => Boolean(r));
}

function resolveSearch(query: string, sessionId: string): TurnResponse {
  const q = query.toLowerCase();

  if (q.includes("empty:") || q.includes("xyzzy-no-match")) {
    return { sessionId, intent: "search", agentMessage: "No memories matched that search.", clues: [], results: [] };
  }
  if (q.includes("python") || q.includes("login") || q.includes("error") || q.includes("traceback")) {
    return {
      sessionId,
      intent: "search",
      agentMessage: "I found the screenshot of your Python login error.",
      clues: [],
      results: pick(["py-login-error", "code-auth", "py-traceback"]),
    };
  }
  if (q.includes("osi") || q.includes("cn ") || q.includes("computer network")) {
    return {
      sessionId,
      intent: "search",
      agentMessage: "I found 3 relevant memories about the OSI model.",
      clues: [],
      results: pick(["cn-osi-slide", "cn-osi-hand", "cn-osi-typed"]),
    };
  }
  if (q.includes("normaliz") || q.includes("dbms") || q.includes("database")) {
    return {
      sessionId,
      intent: "search",
      agentMessage: "Here are your database normalization notes.",
      clues: [],
      results: pick(["db-normal-hand", "db-er-diagram"]),
    };
  }
  if (q.includes("receipt") || q.includes("800") || q.includes("spent")) {
    return {
      sessionId,
      intent: "search",
      agentMessage: "Here is the receipt I found.",
      clues: [],
      results: pick(["receipt-cafe"]),
    };
  }
  if (q.includes("architecture") || q.includes("diagram") || q.includes("project")) {
    return {
      sessionId,
      intent: "search",
      agentMessage: "Here is your project architecture diagram.",
      clues: [],
      results: pick(["arch-diagram", "cn-osi-hand"]),
    };
  }
  if (q.includes("meme") || q.includes("confused")) {
    return {
      sessionId,
      intent: "search",
      agentMessage: "Found a meme using visual similarity.",
      clues: [],
      results: pick(["meme-confused"]),
    };
  }
  return {
    sessionId,
    intent: "search",
    agentMessage: "Here is what I found.",
    clues: [],
    results: pick(["cn-osi-slide", "py-login-error", "db-normal-hand"]),
  };
}

function resolveRefine(message: string, sessionId: string): TurnResponse {
  const m = message.toLowerCase();

  if (m.includes("handwritten") && !m.includes("diagram")) {
    return {
      sessionId,
      intent: "refinement",
      agentMessage: "I will prioritize handwritten notes while keeping the OSI context.",
      clues: [clue("clue-handwritten", "Handwritten")],
      results: pick(["cn-osi-hand", "db-normal-hand"]),
    };
  }
  if (m.includes("diagram")) {
    return {
      sessionId,
      intent: "refinement",
      agentMessage: "Refining to notes with a large diagram.",
      clues: [clue("clue-large-diagram", "Large diagram")],
      results: pick(["cn-osi-hand", "arch-diagram"]),
    };
  }
  if (m.includes("last week") || m.includes("recent") || m.includes("yesterday")) {
    return {
      sessionId,
      intent: "refinement",
      agentMessage: "Prioritizing more recent memories.",
      clues: [clue("clue-recent", "Recent")],
      results: pick(["py-login-error", "code-auth"]),
    };
  }
  if (m.includes("no-intent:")) {
    return { sessionId, agentMessage: "(This turn deliberately omits Resolved_Intent.)" };
  }
  return {
    sessionId,
    intent: "refinement",
    agentMessage: "Refined your search.",
    clues: [clue(`clue-${Date.now()}`, message.trim() || "detail")],
    results: pick(["cn-osi-hand"]),
  };
}

export class MockAdapter implements ApiService {
  private readonly latencyMs: number;
  private readonly failAll: boolean;
  private sessionCounter = 0;

  constructor(options: MockAdapterOptions = {}) {
    this.latencyMs = options.latencyMs ?? 650;
    this.failAll = options.failAll ?? false;
  }

  private async simulate(): Promise<void> {
    if (this.failAll) throw new Error("Simulated Backend failure (mock adapter).");
    if (this.latencyMs > 0) await new Promise((r) => setTimeout(r, this.latencyMs));
  }

  private nextSessionId(existing?: string): string {
    if (existing) return existing;
    this.sessionCounter += 1;
    return `mock-session-${this.sessionCounter}`;
  }

  async search(req: SearchRequest): Promise<TurnResponse> {
    await this.simulate();
    return resolveSearch(req.query, this.nextSessionId(req.sessionId));
  }
  async refine(req: RefineRequest): Promise<TurnResponse> {
    await this.simulate();
    return resolveRefine(req.message, req.sessionId);
  }
  async getExplanation(imageId: string): Promise<ExplanationSignal[]> {
    await this.simulate();
    return byId(imageId)?.explanation ?? [];
  }
  async summarize(req: SummarizeRequest): Promise<SummaryResponse> {
    await this.simulate();
    return {
      sessionId: req.sessionId,
      summary: "Your selected memories focus on the OSI model and the seven network layers, with supporting notes on TCP/IP mapping.",
      points: [
        "OSI Model and its seven layers",
        "Physical and Data Link responsibilities",
        "Network Layer routing basics",
        "Transport Layer reliability",
        "Mapping OSI to the TCP/IP stack",
      ],
      usedImageIds: req.imageIds,
    };
  }
  async roadmap(req: RoadmapRequest): Promise<RoadmapResponse> {
    await this.simulate();
    return {
      sessionId: req.sessionId,
      title: "3-Day Revision Roadmap",
      steps: [
        { order: 1, title: "OSI fundamentals", detail: "Layers 1-3: Physical, Data Link, Network.", sourceImageIds: req.imageIds.slice(0, 1) },
        { order: 2, title: "Data Link + Network Layer", detail: "Framing, MAC, IP addressing and routing.", sourceImageIds: req.imageIds.slice(0, 2) },
        { order: 3, title: "Transport + Application Layer", detail: "TCP/UDP, ports, and common protocols.", sourceImageIds: req.imageIds },
      ],
    };
  }
  async proposeSchedule(req: ScheduleProposeRequest): Promise<ScheduleProposal> {
    await this.simulate();
    return {
      sessionId: req.sessionId,
      events: [
        { title: "Review the OSI model", start: "2026-09-02T09:00:00.000Z", end: "2026-09-02T10:00:00.000Z", notes: "Study session (proposed)." },
        { title: "Study TCP/IP mapping", start: "2026-09-03T09:00:00.000Z", end: "2026-09-03T10:00:00.000Z" },
      ],
    };
  }
  async confirmSchedule(_req: ScheduleConfirmRequest): Promise<{ confirmed: boolean }> {
    await this.simulate();
    return { confirmed: true };
  }
  async uploadImage(file: File): Promise<ImageStatus> {
    await this.simulate();
    return { imageId: `mock-upload-${file.name}`, status: "processing" };
  }
  async getImageStatus(imageId: string): Promise<ImageStatus> {
    await this.simulate();
    return { imageId, status: "ready" };
  }
}
