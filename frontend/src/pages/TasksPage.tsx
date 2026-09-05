import { useMemo, useState } from "react";
import { Icon } from "../components/Icon";
import { useTasks } from "../hooks/useTasks";
import { AddTaskModal } from "../features/tasks/AddTaskModal";
import { formatLongDate, formatTime } from "../features/calendar/calendarUtils";
import type { TaskItem } from "../api/calendarTasks";

export function TasksPage() {
  const { tasks, status, createTask, toggleComplete, deleteTask } = useTasks();
  const [adding, setAdding] = useState(false);
  const [showCompleted, setShowCompleted] = useState(true);

  const groups = useMemo(() => {
    const visible = showCompleted ? tasks : tasks.filter((t) => !t.completed);
    const byDate = new Map<string, TaskItem[]>();
    for (const t of visible) {
      const list = byDate.get(t.due_date) ?? [];
      list.push(t);
      byDate.set(t.due_date, list);
    }
    // sort dates ascending; within a date, incomplete first then by time
    return [...byDate.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([date, items]) => ({
        date,
        items: items.sort((a, b) => {
          if (a.completed !== b.completed) return a.completed ? 1 : -1;
          return (a.due_time ?? "").localeCompare(b.due_time ?? "");
        }),
      }));
  }, [tasks, showCompleted]);

  const remaining = tasks.filter((t) => !t.completed).length;

  return (
    <div className="tasks-page">
      <div className="cal-toolbar">
        <div className="cal-title">
          <h1>Tasks</h1>
          <p className="results-meta">{remaining} open · {tasks.length} total</p>
        </div>
        <div className="cal-controls">
          <label className="ct-toggle">
            <input type="checkbox" checked={showCompleted} onChange={(e) => setShowCompleted(e.target.checked)} />
            Show completed
          </label>
          <button className="btn btn-primary" onClick={() => setAdding(true)}>
            <Icon name="tasks" size={16} /> Add Task
          </button>
        </div>
      </div>

      {status === "loading" ? (
        <div className="ct-empty"><p className="card-desc">Loading tasks…</p></div>
      ) : status === "error" ? (
        <div className="ct-empty">
          <div className="ct-empty-icon"><Icon name="tasks" size={26} /></div>
          <strong>Couldn’t load tasks</strong>
          <p className="card-desc">Please try again.</p>
        </div>
      ) : groups.length === 0 ? (
        <div className="ct-empty">
          <div className="ct-empty-icon"><Icon name="tasks" size={26} /></div>
          <strong>No tasks yet</strong>
          <p className="card-desc">Add your first task to get organized.</p>
          <button className="btn btn-primary" style={{ marginTop: 14 }} onClick={() => setAdding(true)}>
            <Icon name="tasks" size={16} /> Add Task
          </button>
        </div>
      ) : (
        <div className="task-groups">
          {groups.map((g) => (
            <section className="task-group" key={g.date}>
              <div className="task-group-date">{formatLongDate(g.date)}</div>
              <ul className="task-list">
                {g.items.map((t) => (
                  <li className={`task-row ${t.completed ? "done" : ""}`} key={t.id}>
                    <button
                      className={`task-check ${t.completed ? "checked" : ""}`}
                      role="checkbox"
                      aria-checked={t.completed}
                      aria-label={t.completed ? "Mark incomplete" : "Mark complete"}
                      onClick={() => toggleComplete(t.id, !t.completed)}
                    >
                      {t.completed && <Icon name="check" size={14} />}
                    </button>
                    <div className="task-main">
                      <span className="task-title">{t.title}</span>
                      <span className="task-meta">
                        <span className={`ct-priority-dot ${t.priority}`} title={`${t.priority} priority`} />
                        {t.due_time ? formatTime(t.due_time) : "Anytime"}
                      </span>
                    </div>
                    <button className="icon-btn" aria-label="Remove task" onClick={() => deleteTask(t.id)}>
                      <Icon name="close" size={15} />
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      {adding && (
        <AddTaskModal onCancel={() => setAdding(false)} onCreate={async (input) => { await createTask(input); }} />
      )}
    </div>
  );
}
