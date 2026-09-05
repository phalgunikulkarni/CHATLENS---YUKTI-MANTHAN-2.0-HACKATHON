import { useState } from "react";
import { Icon } from "../../components/Icon";
import { AddEventModal } from "../calendar/AddEventModal";
import { AddTaskModal } from "../tasks/AddTaskModal";
import { todayISO } from "../calendar/calendarUtils";
import { useDispatch } from "../../hooks";
import { uid } from "../../utils/format";
import { confirmAddCalendar, confirmAddTask, IS_AGENT_BACKEND } from "../../api/agentActions";
import { calendarTasksService } from "../../api/calendarTasksClient";

/**
 * Reusable "Add to Calendar" / "Add Task" actions for the chat/result UI.
 *
 * Confirmation-before-mutation: the Add modals include an explicit Review ->
 * Confirm step; nothing is created until the user confirms. On confirmation the
 * action is dispatched through the backend orchestrator + functional agent
 * (add_calendar / add_task) when a backend is configured, otherwise it falls
 * back to the direct calendar/task service (offline/demo).
 *
 * `defaultTitle`/`defaultDate` let a caller prefill from a chat suggestion.
 */
interface Props {
  defaultTitle?: string;
  defaultDate?: string;
  compact?: boolean;
}

export function AddToCalendarButton({ defaultTitle, defaultDate, compact }: Props) {
  const dispatch = useDispatch();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className={compact ? "btn btn-subtle" : "btn btn-ghost"} onClick={() => setOpen(true)}>
        <Icon name="calendar" size={15} /> Add to Calendar
      </button>
      {open && (
        <AddEventModal
          defaultDate={defaultDate || todayISO()}
          onCancel={() => setOpen(false)}
          onCreate={async (input) => {
            const payload = { ...input, title: input.title || defaultTitle || "" };
            try {
              if (IS_AGENT_BACKEND) await confirmAddCalendar(payload);
              else await calendarTasksService.createCalendarEvent(payload);
              dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Added to Calendar", tone: "success" } });
            } catch {
              dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Could not add event", tone: "error" } });
            }
          }}
        />
      )}
    </>
  );
}

export function AddTaskButton({ defaultTitle, defaultDate, compact }: Props) {
  const dispatch = useDispatch();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className={compact ? "btn btn-subtle" : "btn btn-ghost"} onClick={() => setOpen(true)}>
        <Icon name="tasks" size={15} /> Add Task
      </button>
      {open && (
        <AddTaskModal
          defaultDate={defaultDate}
          onCancel={() => setOpen(false)}
          onCreate={async (input) => {
            const payload = { ...input, title: input.title || defaultTitle || "" };
            try {
              if (IS_AGENT_BACKEND) await confirmAddTask(payload);
              else await calendarTasksService.createTask(payload);
              dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Task Added", tone: "success" } });
            } catch {
              dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Could not add task", tone: "error" } });
            }
          }}
        />
      )}
    </>
  );
}
