import { useState } from "react";
import type { RoadmapResponse } from "../../api/types";
import { Icon } from "../../components/Icon";

export function RoadmapPanel({ roadmap, onSchedule }: { roadmap: RoadmapResponse; onSchedule: () => void }) {
  const [done, setDone] = useState<Set<number>>(new Set());
  const toggle = (order: number) => {
    setDone((prev) => {
      const next = new Set(prev);
      if (next.has(order)) { next.delete(order); } else { next.add(order); }
      return next;
    });
  };
  const progress = Math.round((done.size / Math.max(roadmap.steps.length, 1)) * 100);

  return (
    <div className="panel">
      <div className="panel-head">
        <Icon name="map" size={18} style={{ color: "var(--accent)" }} />
        <h3>{roadmap.title ?? "Revision Roadmap"}</h3>
      </div>
      <div className="panel-body">
        <div className="progress" aria-label={`Progress ${progress} percent`}>
          <span style={{ width: `${progress}%` }} />
        </div>
        <p className="card-date" style={{ margin: "6px 0 16px" }}>{progress}% complete</p>

        {roadmap.steps.map((step) => (
          <div className="roadmap-day" key={step.order}>
            <div className="day-badge">DAY<br />{step.order}</div>
            <div className="day-card">
              <button
                className="check-row"
                onClick={() => toggle(step.order)}
                aria-pressed={done.has(step.order)}
                style={{ background: "none", border: "none", padding: 0, cursor: "pointer", width: "100%" }}
              >
                <span className="dot" style={{ color: done.has(step.order) ? "#16a34a" : "var(--muted)" }}>
                  {done.has(step.order) && <Icon name="check" size={11} />}
                </span>
                <span style={{ textDecoration: done.has(step.order) ? "line-through" : "none" }}>{step.title}</span>
              </button>
              {step.detail && <p className="card-desc" style={{ marginTop: 6, marginLeft: 26 }}>{step.detail}</p>}
            </div>
          </div>
        ))}

        <button className="btn btn-ghost" style={{ marginTop: 8, width: "100%" }} onClick={onSchedule}>
          <Icon name="calendar" size={16} /> Schedule this
        </button>
      </div>
    </div>
  );
}
