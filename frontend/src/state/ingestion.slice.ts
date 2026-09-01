import type { ProcessingStatus } from "../api/types";
import type { IngestionState, UploadItem, UploadValidation } from "./types";

export const initialIngestionState: IngestionState = { queue: [] };

export type IngestionAction =
  | { type: "FILES_QUEUED"; items: UploadItem[] }
  | { type: "UPLOAD_ITEM_REMOVED"; id: string }
  | { type: "UPLOAD_STATUS_CHANGED"; id: string; status: ProcessingStatus; progress: number }
  | { type: "UPLOAD_FAILED"; id: string; message: string }
  | { type: "UPLOAD_QUEUE_CLEARED" };

function update(queue: UploadItem[], id: string, patch: Partial<UploadItem>): UploadItem[] {
  return queue.map((it) => (it.id === id ? { ...it, ...patch } : it));
}

export function ingestionReducer(state: IngestionState, action: IngestionAction): IngestionState {
  switch (action.type) {
    case "FILES_QUEUED":
      return { ...state, queue: [...state.queue, ...action.items] };
    case "UPLOAD_ITEM_REMOVED":
      return { ...state, queue: state.queue.filter((it) => it.id !== action.id) };
    case "UPLOAD_STATUS_CHANGED":
      return { ...state, queue: update(state.queue, action.id, { status: action.status, progress: action.progress, error: undefined }) };
    case "UPLOAD_FAILED":
      return { ...state, queue: update(state.queue, action.id, { status: "failed", error: action.message }) };
    case "UPLOAD_QUEUE_CLEARED":
      return { ...state, queue: [] };
    default:
      return state;
  }
}

/** Client-side validation partition helper (pure). */
export const ACCEPTED_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];
export const MAX_BYTES = 10 * 1024 * 1024;

export function validateFile(type: string, size: number): UploadValidation {
  if (!ACCEPTED_TYPES.includes(type)) {
    return { valid: false, error: "Unsupported file type. Use PNG, JPEG, WEBP or GIF." };
  }
  if (size > MAX_BYTES) {
    return { valid: false, error: "File is larger than 10 MB." };
  }
  return { valid: true };
}
