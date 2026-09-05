/**
 * Selects the Calendar/Tasks service implementation.
 *
 * Priority:
 *   1. HttpCalendarTasks  - when a backend base URL is configured. The
 *      ChatLens-owned calendar/task endpoints live on the SAME backend as the
 *      rest of the API, so we default to VITE_API_BASE_URL. A separate
 *      VITE_CALENDAR_TASKS_API may override it if the endpoints are hosted
 *      elsewhere.
 *   2. LocalCalendarTasksStore - fallback ONLY when no backend is configured
 *      (e.g. pure offline/demo). Not the production path once a backend exists.
 */
import type { CalendarTasksService } from "./calendarTasks";
import { LocalCalendarTasksStore } from "./adapters/localCalendarTasksStore";
import { HttpCalendarTasks } from "./adapters/httpCalendarTasks";

function backendUrl(): string {
  const dedicated = import.meta.env.VITE_CALENDAR_TASKS_API?.trim();
  if (dedicated) return dedicated;
  return import.meta.env.VITE_API_BASE_URL?.trim() || "";
}

export function createCalendarTasksService(): CalendarTasksService {
  const url = backendUrl();
  if (url) return new HttpCalendarTasks(url);
  return new LocalCalendarTasksStore();
}

export const calendarTasksService: CalendarTasksService = createCalendarTasksService();

/** True when a backend serves the calendar/tasks endpoints (HTTP mode active). */
export const IS_CALENDAR_TASKS_BACKEND = Boolean(backendUrl());
