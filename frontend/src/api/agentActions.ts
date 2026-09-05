/**
 * Frontend seam for CONFIRMED chat actions that flow through the backend
 * orchestrator + functional agents (add_calendar / add_task).
 *
 * This is used by the chat "Add to Calendar" / "Add Task" quick actions. The
 * Calendar and Tasks PAGES use the direct REST adapter (calendarTasksClient);
 * both ultimately hit the same account-isolated backend services. Nothing is
 * created unless `confirmed: true` is sent (the UI confirms first).
 *
 * Account identity is attached via the same X-Account-Id mechanism as the rest
 * of the app (accountContext.getAccountId).
 */
import { getAccountId } from "./accountContext";
import type { CalendarEvent, NewCalendarEvent, NewTaskItem, TaskItem } from "./calendarTasks";

function baseUrl(): string {
  const dedicated = import.meta.env.VITE_CALENDAR_TASKS_API?.trim();
  if (dedicated) return dedicated;
  return import.meta.env.VITE_API_BASE_URL?.trim() || "";
}

function headers(): Record<string, string> {
  const id = getAccountId();
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (id) h["X-Account-Id"] = id;
  return h;
}

interface AgentResultEnvelope<T> {
  ok: boolean;
  agent: string;
  message: string;
  data: T;
  evidence: unknown[];
  metadata: Record<string, unknown>;
  error: string | null;
}

/** True when a backend is configured to accept agent actions. */
export const IS_AGENT_BACKEND = Boolean(baseUrl());

async function dispatchAction<T>(agent: string, confirmed: boolean, params: Record<string, unknown>): Promise<AgentResultEnvelope<T>> {
  const url = `${baseUrl().replace(/\/$/, "")}/api/agents/action`;
  const res = await fetch(url, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ agent, confirmed, params }),
  });
  const body = (await res.json().catch(() => null)) as AgentResultEnvelope<T> | { detail?: string } | null;
  if (!res.ok) {
    const detail = body && "detail" in body ? body.detail : undefined;
    throw new Error(detail || `Agent action failed (HTTP ${res.status})`);
  }
  return body as AgentResultEnvelope<T>;
}

/** Create a calendar event through the add_calendar agent (confirmed). */
export async function confirmAddCalendar(input: NewCalendarEvent): Promise<CalendarEvent> {
  const r = await dispatchAction<{ event: CalendarEvent }>("add_calendar", true, { ...input });
  return r.data.event;
}

/** Create a task through the add_task agent (confirmed). */
export async function confirmAddTask(input: NewTaskItem): Promise<TaskItem> {
  const r = await dispatchAction<{ task: TaskItem }>("add_task", true, { ...input });
  return r.data.task;
}
