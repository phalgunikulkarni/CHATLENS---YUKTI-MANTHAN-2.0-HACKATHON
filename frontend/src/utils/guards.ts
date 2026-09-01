/** Presence guards so absent Backend fields render nothing (no fabrication). */
export function hasText(v: string | undefined | null): v is string {
  return typeof v === "string" && v.trim().length > 0;
}

export function hasNumber(v: number | undefined | null): v is number {
  return typeof v === "number" && !Number.isNaN(v);
}

export function hasItems<T>(v: T[] | undefined | null): v is T[] {
  return Array.isArray(v) && v.length > 0;
}
