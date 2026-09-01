import { useRef } from "react";
import type { ScheduleProposal } from "../../api/types";
import { useFocusTrap } from "../../hooks";
import { Icon } from "../../components/Icon";

interface Props {
  proposal: ScheduleProposal;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Schedule confirmation dialog. Focus-trapped. A confirmation request is only
 * sent when the user activates Confirm (Cancel/Escape sends nothing).
 */
export function ConfirmDialog({ proposal, onConfirm, onCancel }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, true, onCancel);

  return (
    <div className="dialog-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onCancel(); }}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title" ref={ref}>
        <div className="dialog-head">
          <div className="section-title" id="confirm-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Icon name="calendar" size={18} style={{ color: "var(--accent)" }} /> Confirm calendar events
          </div>
          <p className="card-desc" style={{ marginTop: 8 }}>
            Review the proposed schedule. Nothing is added to your calendar until you confirm.
          </p>
        </div>
        <div className="dialog-body">
          {proposal.events.map((ev, i) => (
            <div className="event-row" key={i}>
              <span className="event-dot" />
              <div>
                <div style={{ fontWeight: 700, color: "var(--navy)" }}>{ev.title}</div>
                <div className="card-date">
                  {new Date(ev.start).toLocaleString()}
                  {ev.end ? ` - ${new Date(ev.end).toLocaleTimeString()}` : ""}
                </div>
                {ev.notes && <p className="card-desc" style={{ marginTop: 4 }}>{ev.notes}</p>}
              </div>
            </div>
          ))}
        </div>
        <div className="dialog-foot">
          <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" onClick={onConfirm}>
            <Icon name="check" size={16} /> Confirm &amp; schedule
          </button>
        </div>
      </div>
    </div>
  );
}
