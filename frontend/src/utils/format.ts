export function formatScore(score: number): string {
  return `${Math.round(score * 100)}%`;
}

export function formatDate(iso: string | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/** Honest relative time from a real epoch-ms timestamp the user actually created. */
export function formatRelative(at: number, now: number = Date.now()): string {
  const diff = Math.max(0, now - at);
  const sec = Math.floor(diff / 1000);
  if (sec < 45) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} minute${min === 1 ? "" : "s"} ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} hour${hr === 1 ? "" : "s"} ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day} day${day === 1 ? "" : "s"} ago`;
  return new Date(at).toLocaleDateString();
}

export function uid(prefix = "id"): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}-${Date.now().toString(36)}`;
}

export const CATEGORY_LABEL: Record<string, string> = {
  screenshot: "Screenshot",
  note: "Notes",
  code: "Code",
  receipt: "Receipt",
  document: "Document",
  slide: "Slide",
  other: "Other",
};
/** Human labels for memory sources (used by badges and filters). */
export const SOURCE_LABEL: Record<string, string> = {
  uploaded: "Uploaded",
  whatsapp: "WhatsApp",
  telegram: "Telegram",
  google_drive: "Google Drive",
  google_photos: "Google Photos",
};
