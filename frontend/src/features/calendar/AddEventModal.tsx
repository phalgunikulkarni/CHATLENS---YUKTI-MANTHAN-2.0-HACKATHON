import { useRef, useState } from "react";
import { Icon } from "../../components/Icon";
import { useFocusTrap } from "../../hooks";
import type { NewCalendarEvent } from "../../api/calendarTasks";
import { formatLongDate, formatTime, localTimezone } from "./calendarUtils";

interface Props {
  /** Pre-fill the date (e.g. the day the user clicked). */
  defaultDate: string;
  onCancel: () => void;
  onCreate: (input: NewCalendarEvent) => Promise<unknown>;
}

const REMINDER_OPTIONS = ["None", "At time of event", "10 minutes", "30 minutes", "1 hour", "1 day"];

/**
 * Add-event flow with an explicit confirmation step. Nothing is created until
 * the user confirms on the review screen. Reuses the shared dialog styling.
 */
export function AddEventModal({ defaultDate, onCancel, onCreate }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, true, onCancel);

  const [step, setStep] = useState<"form" | "confirm">("form");
  const [submitting, setSubmitting] = useState(false);

  const [title, setTitle] = useState("");
  const [date, setDate] = useState(defaultDate);
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("");
  const [participants, setParticipants] = useState("");
  const [reminder, setReminder] = useState("None");

  const canReview = title.trim() && date && startTime;

  const buildPayload = (): NewCalendarEvent => ({
    title: title.trim(),
    date,
    start_time: startTime,
    end_time: endTime || null,
    timezone: localTimezone(),
    participants: participants.trim(),
    reminder: reminder === "None" ? null : reminder,
  });

  const confirm = async () => {
    setSubmitting(true);
    await onCreate(buildPayload());
    setSubmitting(false);
    onCancel(); // close; success toast is shown by the hook
  };

  return (
    <div className="dialog-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onCancel(); }}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="add-event-title" ref={ref}>
        <div className="dialog-head">
          <div className="section-title" id="add-event-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Icon name="calendar" size={18} style={{ color: "var(--accent)" }} />
            {step === "form" ? "Add event" : "Confirm event"}
          </div>
          <p className="card-desc" style={{ marginTop: 8 }}>
            {step === "form"
              ? "Create an event in your ChatLens calendar."
              : "Review the details. Nothing is added until you confirm."}
          </p>
        </div>

        {step === "form" ? (
          <div className="dialog-body ct-form">
            <label className="ct-field">
              <span>Title</span>
              <input className="ct-input" value={title} autoFocus
                     onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Team sync" />
            </label>
            <div className="ct-grid-2">
              <label className="ct-field">
                <span>Date</span>
                <input className="ct-input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
              </label>
              <label className="ct-field">
                <span>Start time</span>
                <input className="ct-input" type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
              </label>
            </div>
            <div className="ct-grid-2">
              <label className="ct-field">
                <span>End time (optional)</span>
                <input className="ct-input" type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
              </label>
              <label className="ct-field">
                <span>Reminder (optional)</span>
                <select className="ct-input" value={reminder} onChange={(e) => setReminder(e.target.value)}>
                  {REMINDER_OPTIONS.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </label>
            </div>
            <label className="ct-field">
              <span>Participants / details (optional)</span>
              <textarea className="ct-input" rows={3} value={participants}
                        onChange={(e) => setParticipants(e.target.value)}
                        placeholder="Who's involved, location, notes..." />
            </label>
          </div>
        ) : (
          <div className="dialog-body">
            <div className="event-row">
              <span className="event-dot" />
              <div>
                <div style={{ fontWeight: 700, color: "var(--navy)" }}>{title.trim()}</div>
                <div className="card-date">
                  {formatLongDate(date)} · {formatTime(startTime)}
                  {endTime ? ` – ${formatTime(endTime)}` : ""}
                </div>
                {participants.trim() && <p className="card-desc" style={{ marginTop: 4 }}>{participants.trim()}</p>}
                {reminder !== "None" && (
                  <p className="card-desc" style={{ marginTop: 4 }}>Reminder: {reminder}</p>
                )}
              </div>
            </div>
          </div>
        )}

        <div className="dialog-foot">
          {step === "form" ? (
            <>
              <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
              <button className="btn btn-primary" disabled={!canReview} onClick={() => setStep("confirm")}>
                Review
              </button>
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
