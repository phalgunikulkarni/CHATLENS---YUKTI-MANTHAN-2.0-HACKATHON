import { useCallback, useEffect, useState } from "react";
import { calendarTasksService } from "../api/calendarTasksClient";
import type { NewTaskItem, TaskItem } from "../api/calendarTasks";
import { useDispatch } from "./index";
import { uid } from "../utils/format";

type Status = "idle" | "loading" | "ready" | "error";

/** Owns task state + create/toggle/delete, with toast success/error states. */
export function useTasks() {
  const dispatch = useDispatch();
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [status, setStatus] = useState<Status>("idle");

  const reload = useCallback(async () => {
    setStatus("loading");
    try {
      setTasks(await calendarTasksService.fetchTasks());
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const createTask = useCallback(
    async (input: NewTaskItem): Promise<TaskItem | null> => {
      try {
        const created = await calendarTasksService.createTask(input);
        setTasks((prev) => [...prev, created]);
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Task Added", tone: "success" } });
        return created;
      } catch {
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Could not add task", tone: "error" } });
        return null;
      }
    },
    [dispatch],
  );

  const toggleComplete = useCallback(
    async (id: string, completed: boolean) => {
      // optimistic
      setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, completed } : t)));
      try {
        await calendarTasksService.updateTask(id, { completed });
      } catch {
        setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, completed: !completed } : t)));
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Could not update task", tone: "error" } });
      }
    },
    [dispatch],
  );

  const deleteTask = useCallback(
    async (id: string) => {
      try {
        await calendarTasksService.deleteTask(id);
        setTasks((prev) => prev.filter((t) => t.id !== id));
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Task removed", tone: "info" } });
      } catch {
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Could not remove task", tone: "error" } });
      }
    },
    [dispatch],
  );

  return { tasks, status, reload, createTask, toggleComplete, deleteTask };
}
