/** Small, dependency-free date helpers for the month-grid calendar. */

export const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
export const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** "YYYY-MM-DD" for a Date in LOCAL time (no UTC shift). */
export function toISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function todayISO(): string {
  return toISODate(new Date());
}

export interface DayCell {
  date: Date;
  iso: string;
  inMonth: boolean;
  isToday: boolean;
}

/**
 * Build a 6-row (42-cell) grid covering the given month, padded with the
 * trailing/leading days of adjacent months (Google-Calendar style).
 */
export function buildMonthGrid(year: number, month: number): DayCell[] {
  const first = new Date(year, month, 1);
  const startOffset = first.getDay(); // 0=Sun
  const gridStart = new Date(year, month, 1 - startOffset);
  const today = todayISO();
  const cells: DayCell[] = [];
  for (let i = 0; i < 42; i++) {
    const date = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + i);
    const iso = toISODate(date);
    cells.push({ date, iso, inMonth: date.getMonth() === month, isToday: iso === today });
  }
  return cells;
}

/** Local IANA timezone (best-effort; falls back to UTC). */
export function localTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

/** Human label for an ISO date, e.g. "September 5, 2026". */
export function formatLongDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${MONTHS[m - 1]} ${d}, ${y}`;
}

/** "HH:MM" 24h -> "h:MM AM/PM". */
export function formatTime(hhmm: string | null): string {
  if (!hhmm) return "";
  const [h, m] = hhmm.split(":").map(Number);
  if (Number.isNaN(h)) return hhmm;
  const period = h >= 12 ? "PM" : "AM";
  const hour = h % 12 === 0 ? 12 : h % 12;
  return `${hour}:${String(m ?? 0).padStart(2, "0")} ${period}`;
}
