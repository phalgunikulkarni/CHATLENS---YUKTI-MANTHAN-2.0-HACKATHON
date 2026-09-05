import { useMemo, useState } from "react";
import { Icon } from "../components/Icon";
import { useCalendar } from "../hooks/useCalendar";
import { AddEventModal } from "../features/calendar/AddEventModal";
import {
  MONTHS, WEEKDAYS, buildMonthGrid, formatLongDate, formatTime, todayISO, toISODate,
} from "../features/calendar/calendarUtils";
import type { CalendarEvent } from "../api/calendarTasks";

export function CalendarPage() {
  const { events, status, createEvent, deleteEvent } = useCalendar();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [selectedISO, setSelectedISO] = useState<string>(todayISO());
  const [adding, setAdding] = useState<string | null>(null); // holds default date

  const grid = useMemo(() => buildMonthGrid(year, month), [year, month]);

  const eventsByDate = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const e of events) {
      const list = map.get(e.date) ?? [];
      list.push(e);
      map.set(e.date, list);
    }
    for (const list of map.values()) list.sort((a, b) => a.start_time.localeCompare(b.start_time));
    return map;
  }, [events]);

  const selectedEvents = eventsByDate.get(selectedISO) ?? [];

  const prevMonth = () => {
    const d = new Date(year, month - 1, 1);
    setYear(d.getFullYear()); setMonth(d.getMonth());
  };
  const nextMonth = () => {
    const d = new Date(year, month + 1, 1);
    setYear(d.getFullYear()); setMonth(d.getMonth());
  };
  const goToday = () => {
    const t = new Date();
    setYear(t.getFullYear()); setMonth(t.getMonth()); setSelectedISO(toISODate(t));
  };

  return (
    <div className="cal-page">
      <div className="cal-toolbar">
        <div className="cal-title">
          <h1>{MONTHS[month]} {year}</h1>
        </div>
        <div className="cal-controls">
          <button className="icon-btn" aria-label="Previous month" onClick={prevMonth}>
            <Icon name="chevron" size={18} style={{ transform: "rotate(180deg)" }} />
          </button>
          <button className="btn btn-ghost" onClick={goToday}>Today</button>
          <button className="icon-btn" aria-label="Next month" onClick={nextMonth}>
            <Icon name="chevron" size={18} />
          </button>
          <button className="btn btn-primary" onClick={() => setAdding(selectedISO)}>
            <Icon name="calendar" size={16} /> Add Event
          </button>
        </div>
      </div>

      <div className="cal-layout">
        <div className="cal-grid-wrap">
          <div className="cal-weekdays">
            {WEEKDAYS.map((w) => <div key={w} className="cal-weekday">{w}</div>)}
          </div>
          <div className="cal-grid">
            {grid.map((cell) => {
              const dayEvents = eventsByDate.get(cell.iso) ?? [];
              const selected = cell.iso === selectedISO;
              return (
                <button
                  key={cell.iso}
                  className={`cal-cell ${cell.inMonth ? "" : "muted"} ${cell.isToday ? "today" : ""} ${selected ? "selected" : ""}`}
                  onClick={() => setSelectedISO(cell.iso)}
                  aria-current={cell.isToday ? "date" : undefined}
                >
                  <span className="cal-daynum">{cell.date.getDate()}</span>
                  <span className="cal-events">
                    {dayEvents.slice(0, 3).map((e) => (
                      <span key={e.id} className="cal-event-pill" title={`${formatTime(e.start_time)} ${e.title}`}>
                        {formatTime(e.start_time)} {e.title}
                      </span>
                    ))}
                    {dayEvents.length > 3 && <span className="cal-more">+{dayEvents.length - 3} more</span>}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <aside className="cal-day-panel">
          <div className="cal-day-head">
            <div className="section-title" style={{ marginBottom: 4 }}>{formatLongDate(selectedISO)}</div>
            <button className="btn btn-subtle" onClick={() => setAdding(selectedISO)}>
              <Icon name="calendar" size={15} /> Add
            </button>
          </div>

          {status === "loading" ? (
            <div className="ct-empty"><p className="card-desc">Loading events…</p></div>
          ) : status === "error" ? (
            <div className="ct-empty"><p className="card-desc">Couldn’t load events.</p></div>
          ) : selectedEvents.length === 0 ? (
            <div className="ct-empty">
              <div className="ct-empty-icon"><Icon name="calendar" size={26} /></div>
              <strong>No events</strong>
              <p className="card-desc">Nothing scheduled for this day yet.</p>
            </div>
          ) : (
            <div className="cal-event-list">
              {selectedEvents.map((e) => (
                <div className="cal-event-card" key={e.id}>
                  <div className="cal-event-time">
                    {formatTime(e.start_time)}{e.end_time ? ` – ${formatTime(e.end_time)}` : ""}
                  </div>
                  <div className="cal-event-main">
                    <div className="cal-event-title">{e.title}</div>
                    {e.participants && <p className="card-desc">{e.participants}</p>}
                    {e.reminder && <span className="ct-badge">Reminder: {e.reminder}</span>}
                  </div>
                  <button className="icon-btn" aria-label="Remove event" onClick={() => deleteEvent(e.id)}>
                    <Icon name="close" size={15} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </aside>
      </div>

      {adding !== null && (
        <AddEventModal
          defaultDate={adding}
          onCancel={() => setAdding(null)}
          onCreate={async (input) => { await createEvent(input); setSelectedISO(input.date); }}
        />
      )}
    </div>
  );
}
