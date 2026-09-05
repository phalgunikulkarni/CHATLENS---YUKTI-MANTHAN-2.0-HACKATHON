import { useCallback, useEffect, useState } from "react";
import { calendarTasksService } from "../api/calendarTasksClient";
import type { CalendarEvent, NewCalendarEvent } from "../api/calendarTasks";
import { useDispatch } from "./index";
import { uid } from "../utils/format";

type Status = "idle" | "loading" | "ready" | "error";

/** Owns calendar event state + create/delete, with toast success/error states. */
export function useCalendar() {
  const dispatch = useDispatch();
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [status, setStatus] = useState<Status>("idle");

  const reload = useCallback(async () => {
    setStatus("loading");
    try {
      setEvents(await calendarTasksService.fetchCalendarEvents());
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const createEvent = useCallback(
    async (input: NewCalendarEvent): Promise<CalendarEvent | null> => {
      try {
        const created = await calendarTasksService.createCalendarEvent(input);
        setEvents((prev) => [...prev, created]);
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Added to Calendar", tone: "success" } });
        return created;
      } catch {
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Could not add event", tone: "error" } });
        return null;
      }
    },
    [dispatch],
  );

  const deleteEvent = useCallback(
    async (id: string) => {
      try {
        await calendarTasksService.deleteCalendarEvent(id);
        setEvents((prev) => prev.filter((e) => e.id !== id));
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Event removed", tone: "info" } });
      } catch {
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Could not remove event", tone: "error" } });
      }
    },
    [dispatch],
  );

  return { events, status, reload, createEvent, deleteEvent };
}
