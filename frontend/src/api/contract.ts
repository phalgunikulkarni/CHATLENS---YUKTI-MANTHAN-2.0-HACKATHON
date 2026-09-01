/**
 * PROPOSED Backend API contract - REQUIRES BACKEND TEAM SIGN-OFF.
 *
 * These endpoints are NOT implemented in this repository. They describe the
 * shape the Frontend expects. Until the backend team confirms them, the app
 * runs against the mock adapter (see client.ts). Do not treat these as real.
 */
export const ENDPOINTS = {
  /** POST - a new natural-language search. */
  search: "/api/search",
  /** POST - a conversational follow-up carrying the active clue set. */
  refine: "/api/refine",
  /** GET - retrieval evidence for a result (or embed on SearchResult.explanation). */
  explanation: (id: string) => `/api/results/${id}/explanation`,
  /** POST - conversational Q&A about a specific retrieved image (LLM-backed). */
  imageQa: "/api/images/qa",
  /** POST - summarize the selected memories. */
  summarize: "/api/actions/summarize",
  /** POST - turn memories into an ordered plan. */
  roadmap: "/api/actions/roadmap",
  /** POST - preview proposed calendar events. */
  schedulePropose: "/api/actions/schedule/propose",
  /** POST - create events only after explicit user confirmation. */
  scheduleConfirm: "/api/actions/schedule/confirm",
  /** POST - upload one image for ingestion. */
  images: "/api/images",
  /** GET - poll processing status for an ingested image. */
  imageStatus: (id: string) => `/api/images/${id}/status`,
} as const;
