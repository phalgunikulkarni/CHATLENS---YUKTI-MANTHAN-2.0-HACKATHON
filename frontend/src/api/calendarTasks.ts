/**
 * Calendar & Tasks service seam.
 *
 * ChatLens owns its OWN calendar and tasks (no external Google/Outlook OAuth).
 * The backend will later provide durable, server-side persistence; until those
 * endpoints exist, an isolated local adapter (localStorage) keeps the UI fully
 * functional using REAL user-entered data (never hard-coded fake records).
 *
 * This mirrors the existing ApiService/adapter pattern: the UI depends ONLY on
 * these interfaces + service functions, so swapping in the real backend later
 * is a one-file change in `calendarTasksClient.ts` and requires no UI rewrite.
 *
 * Data models match the P2S4 expectation and can map cleanly onto backend rows.
 */

export type TaskPriority = "low" | "medium" | "high";

export interface CalendarEvent {
  id: string;
  title: string;
  /** ISO date "YYYY-MM-DD" (the day the event is shown on). */
  date: string;
  /** "HH:MM" 24h local start time. */
  start_time: string;
  /** Optional "HH:MM" 24h local end time. */
  end_time: string | null;
  /** IANA timezone, e.g. "Asia/Kolkata". */
  timezone: string;
  /** Free-form participants/details text. */
  participants: string;
  /** Optional reminder, minutes-before as a string label (e.g. "10 minutes"), or null. */
  reminder: string | null;
  /** Epoch ms when created. */
  created_at: number;
}

export interface TaskItem {
  id: string;
  title: string;
  /** ISO date "YYYY-MM-DD". */
  due_date: string;
  /** Optional "HH:MM" 24h local time. */
  due_time: string | null;
  priority: TaskPriority;
  completed: boolean;
  created_at: number;
}

/** Payloads for creation (server assigns id/created_at in the real backend). */
export type NewCalendarEvent = Omit<CalendarEvent, "id" | "created_at">;
export type NewTaskItem = Omit<TaskItem, "id" | "created_at" | "completed"> & {
  completed?: boolean;
};

/**
 * The single typed boundary for calendar + tasks. The concrete implementation
 * (local vs future HTTP) is selected in calendarTasksClient.ts.
 */
export interface CalendarTasksService {
  fetchCalendarEvents(): Promise<CalendarEvent[]>;
  createCalendarEvent(input: NewCalendarEvent): Promise<CalendarEvent>;
  deleteCalendarEvent(id: string): Promise<void>;

  fetchTasks(): Promise<TaskItem[]>;
  createTask(input: NewTaskItem): Promise<TaskItem>;
  updateTask(id: string, patch: Partial<Omit<TaskItem, "id" | "created_at">>): Promise<TaskItem>;
  deleteTask(id: string): Promise<void>;
}
