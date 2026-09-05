import { useRef, useState } from "react";
import { Icon } from "../../components/Icon";
import { useFocusTrap } from "../../hooks";
import type { NewTaskItem, TaskPriority } from "../../api/calendarTasks";
import { formatLongDate, formatTime, todayISO } from "../calendar/calendarUtils";

interface Props {
  defaultDate?: string;
  /** Optional pre-filled title (e.g. from a selected memory / query context). */
  defaultTitle?: string;
  onCancel: () => void;
  onCreate: (input: NewTaskItem) => Promise<unknown>;
}

const PRIORITIES: TaskPriority[] = ["low", "medium", "high"];

/** Add-task flow with an explicit confirmation step before creation. */
export function AddTaskModal({ defaultDate, defaultTitle, onCancel, onCreate }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, true, onCancel);

  const [step, setStep] = useState<"form" | "confirm">("form");
  const [submitting, setSubmitting] = useState(false);

  const [title, setTitle] = useState(defaultTitle ?? "");
  const [dueDate, setDueDate] = useState(defaultDate || todayISO());
  const [dueTime, setDueTime] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("medium");

  const canReview = title.trim() && dueDate;

  const buildPayload = (): NewTaskItem => ({
    title: title.trim(),
    due_date: dueDate,
    due_time: dueTime || null,
    priority,
  });

  const confirm = async () => {
    setSubmitting(true);
    await onCreate(buildPayload());
    setSubmitting(false);
    onCancel();
  };

  return (
    <div className="dialog-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onCancel(); }}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="add-task-title" ref={ref}>
        <div className="dialog-head">
          <div className="section-title" id="add-task-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Icon name="tasks" size={18} style={{ color: "var(--accent)" }} />
            {step === "form" ? "Add task" : "Confirm task"}
          </div>
          <p className="card-desc" style={{ marginTop: 8 }}>
            {step === "form"
              ? "Create a task in your ChatLens tasks."
              : "Review the details. The task is created only when you confirm."}
          </p>
        </div>

        {step === "form" ? (
          <div className="dialog-body ct-form">
            <label className="ct-field">
              <span>Title</span>
              <input className="ct-input" value={title} autoFocus
                     onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Submit assignment" />
            </label>
            <div className="ct-grid-2">
              <label className="ct-field">
                <span>Due date</span>
                <input className="ct-input" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
              </label>
              <label className="ct-field">
                <span>Due time (optional)</span>
                <input className="ct-input" type="time" value={dueTime} onChange={(e) => setDueTime(e.target.value)} />
              </label>
            </div>
            <label className="ct-field">
              <span>Priority</span>
              <div className="ct-priority-row">
                {PRIORITIES.map((p) => (
                  <button
                    key={p}
                    type="button"
                    className={`ct-priority ${p} ${priority === p ? "active" : ""}`}
                    onClick={() => setPriority(p)}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </label>
          </div>
        ) : (
          <div className="dialog-body">
            <div className="event-row">
              <span className={`ct-priority-dot ${priority}`} />
              <div>
                <div style={{ fontWeight: 700, color: "var(--navy)" }}>{title.trim()}</div>
                <div className="card-date">
                  {formatLongDate(dueDate)}{dueTime ? ` · ${formatTime(dueTime)}` : ""}
                </div>
                <span className={`ct-badge ct-badge-${priority}`}>{priority} priority</span>
              </div>
            </div>
          </div>
        )}

        <div className="dialog-foot">
          {step === "form" ? (
            <>
              <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
              <button className="btn btn-primary" disabled={!canReview} onClick={() => setStep("confirm")}>Review</button>
            </>
          ) : (
            <>
              <button className="btn btn-ghost" onClick={() => setStep("form")} disabled={submitting}>Back</button>
              <button className="btn btn-primary" onClick={confirm} disabled={submitting}>
                <Icon name="check" size={16} /> {submitting ? "Adding…" : "Confirm & add"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
