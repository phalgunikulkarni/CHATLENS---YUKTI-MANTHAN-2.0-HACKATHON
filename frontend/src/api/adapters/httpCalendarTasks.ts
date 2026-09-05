/**
 * HTTP adapter for the ChatLens-owned Calendar/Task backend (P2S4 endpoints).
 *
 * Active when a backend base URL is configured (see calendarTasksClient.ts).
 * Attaches the signed-in account via the SAME `X-Account-Id` mechanism the main
 * ApiService uses (accountContext.getAccountId), so calendar/task data is
 * account-isolated. No cookies/credentials and no backend secrets are involved.
 */
import { getAccountId } from "../accountContext";
import type {
  CalendarEvent,
  CalendarTasksService,
  NewCalendarEvent,
  NewTaskItem,
  TaskItem,
} from "../calendarTasks";

export class HttpCalendarTasks implements CalendarTasksService {
  constructor(private readonly baseUrl: string) {}

  private url(path: string): string {
    return `${this.baseUrl.replace(/\/$/, "")}${path}`;
  }

  /** Same account seam as HttpAdapter: attach X-Account-Id when signed in. */
  private headers(base: Record<string, string> = {}): Record<string, string> {
    const id = getAccountId();
    return id ? { ...base, "X-Account-Id": id } : base;
  }

  private async json<T>(res: Response): Promise<T> {
    if (!res.ok) throw new Error(`calendar/tasks API error HTTP ${res.status}`);
    return (await res.json()) as T;
  }

  async fetchCalendarEvents(): Promise<CalendarEvent[]> {
    return this.json(await fetch(this.url("/api/calendar/events"), { headers: this.headers() }));
  }
  async createCalendarEvent(input: NewCalendarEvent): Promise<CalendarEvent> {
    return this.json(
      await fetch(this.url("/api/calendar/events"), {
        method: "POST",
        headers: this.headers({ "Content-Type": "application/json" }),
        body: JSON.stringify(input),
      }),
    );
  }
  async deleteCalendarEvent(id: string): Promise<void> {
    const res = await fetch(this.url(`/api/calendar/events/${encodeURIComponent(id)}`), {
      method: "DELETE",
      headers: this.headers(),
    });
    if (!res.ok) throw new Error(`calendar/tasks API error HTTP ${res.status}`);
  }
  async fetchTasks(): Promise<TaskItem[]> {
    return this.json(await fetch(this.url("/api/tasks"), { headers: this.headers() }));
  }
  async createTask(input: NewTaskItem): Promise<TaskItem> {
    return this.json(
      await fetch(this.url("/api/tasks"), {
        method: "POST",
        headers: this.headers({ "Content-Type": "application/json" }),
        body: JSON.stringify(input),
      }),
    );
  }
  async updateTask(
    id: string,
    patch: Partial<Omit<TaskItem, "id" | "created_at">>,
  ): Promise<TaskItem> {
    return this.json(
      await fetch(this.url(`/api/tasks/${encodeURIComponent(id)}`), {
        method: "PATCH",
        headers: this.headers({ "Content-Type": "application/json" }),
        body: JSON.stringify(patch),
      }),
    );
  }
  async deleteTask(id: string): Promise<void> {
    const res = await fetch(this.url(`/api/tasks/${encodeURIComponent(id)}`), {
      method: "DELETE",
      headers: this.headers(),
    });
    if (!res.ok) throw new Error(`calendar/tasks API error HTTP ${res.status}`);
  }
}
