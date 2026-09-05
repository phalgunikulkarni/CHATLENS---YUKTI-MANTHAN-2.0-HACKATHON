import { Icon } from "../../components/Icon";
import { AddToCalendarButton, AddTaskButton } from "./QuickAddActions";

interface Props {
  selectedCount: number;
  loading: boolean;
  onSummarize: () => void;
  onRoadmap: () => void;
  onExtractKeyPoints: () => void;
  onRelated: () => void;
  /** Prefill for the Add-to-Calendar dialog (selected memory title / query). */
  addToCalendarTitle?: string;
  /** Prefill for the Add-to-Task dialog (selected memory title / query). */
  addTaskTitle?: string;
}

/** Actions on retrieved memories. Enabled once memories are selected. */
export function ActionPanel({
  selectedCount,
  loading,
  onSummarize,
  onRoadmap,
  onExtractKeyPoints,
  onRelated,
  addToCalendarTitle,
  addTaskTitle,
}: Props) {
  const disabled = selectedCount === 0 || loading;
  return (
    <div className="panel">
      <div className="panel-head">
        <Icon name="sparkles" size={18} style={{ color: "var(--accent)" }} />
        <h3>What would you like to do?</h3>
      </div>
      <div className="panel-body">
        <p className="selected-hint">
          {selectedCount === 0
            ? "Select one or more memories to act on them."
            : `${selectedCount} memory${selectedCount > 1 ? "ies" : ""} selected.`}
        </p>
        <div className="action-grid">
          <button className="action-btn" onClick={onSummarize} disabled={disabled}>
            <span className="action-emoji">✨</span> Summarize
          </button>
          <button className="action-btn" onClick={onRoadmap} disabled={disabled}>
            <span className="action-emoji">📚</span> Revision roadmap
          </button>
          <button className="action-btn" onClick={onExtractKeyPoints} disabled={disabled}>
            <span className="action-emoji">📋</span> Extract key points
          </button>
          <button className="action-btn" onClick={onRelated} disabled={disabled}>
            <span className="action-emoji">🔗</span> Related memories
          </button>
        </div>
        {/* Add to Calendar / Add to Task use the shared confirmation dialogs +
            the calendar/task agents. Placed with the other agent actions. */}
        <div className="action-secondary">
          <div data-testid="add-to-calendar-action" style={{ flex: 1 }}>
            <AddToCalendarButton defaultTitle={addToCalendarTitle} compact />
          </div>
          <div data-testid="add-to-task-action" style={{ flex: 1 }}>
            <AddTaskButton defaultTitle={addTaskTitle} compact />
          </div>
        </div>
      </div>
    </div>
  );
}
