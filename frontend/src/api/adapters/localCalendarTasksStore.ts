/**
 * ISOLATED temporary persistence for Calendar & Tasks (localStorage).
 *
 * This is the ONLY place that stores calendar/task data client-side. It exists
 * because the backend calendar/task endpoints are not finalized yet. It persists
 * REAL user-entered records (not fabricated demo data) and is designed to be
 * swapped for the HTTP adapter without touching the UI. All methods are async to
 * match the future network-backed contract.
 */
import type {
  CalendarEvent,
  CalendarTasksService,
  NewCalendarEvent,
  NewTaskItem,
  TaskItem,
} from "../calendarTasks";
import { uid } from "../../utils/format";

const EVENTS_KEY = "chatlens.calendar.events.v1";
const TASKS_KEY = "chatlens.tasks.v1";

function load<T>(key: string): T[] {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as T[]) : [];
  } catch {
    return [];
  }
}

function save<T>(key: string, rows: T[]): void {
  try {
    localStorage.setItem(key, JSON.stringify(rows));
  } catch {
    // Storage full/unavailable: keep the app usable; data just won't persist.
  }
}

export class LocalCalendarTasksStore implements CalendarTasksService {
  async fetchCalendarEvents(): Promise<CalendarEvent[]> {
    return load<CalendarEvent>(EVENTS_KEY);
  }

  async createCalendarEvent(input: NewCalendarEvent): Promise<CalendarEvent> {
    const rows = load<CalendarEvent>(EVENTS_KEY);
    const event: CalendarEvent = { ...input, id: uid("evt"), created_at: Date.now() };
    save(EVENTS_KEY, [...rows, event]);
    return event;
  }

  async deleteCalendarEvent(id: string): Promise<void> {
    const rows = load<CalendarEvent>(EVENTS_KEY).filter((e) => e.id !== id);
    save(EVENTS_KEY, rows);
  }

  async fetchTasks(): Promise<TaskItem[]> {
    return load<TaskItem>(TASKS_KEY);
  }

  async createTask(input: NewTaskItem): Promise<TaskItem> {
    const rows = load<TaskItem>(TASKS_KEY);
    const task: TaskItem = {
      ...input,
      completed: input.completed ?? false,
      id: uid("task"),
      created_at: Date.now(),
    };
    save(TASKS_KEY, [...rows, task]);
    return task;
  }

  async updateTask(
    id: string,
    patch: Partial<Omit<TaskItem, "id" | "created_at">>,
  ): Promise<TaskItem> {
    const rows = load<TaskItem>(TASKS_KEY);
    let updated: TaskItem | null = null;
    const next = rows.map((t) => {
      if (t.id !== id) return t;
      updated = { ...t, ...patch };
      return updated;
    });
    if (!updated) throw new Error(`task ${id} not found`);
    save(TASKS_KEY, next);
    return updated;
  }

  async deleteTask(id: string): Promise<void> {
    const rows = load<TaskItem>(TASKS_KEY).filter((t) => t.id !== id);
    save(TASKS_KEY, rows);
  }
}
