import { Icon } from "../../components/Icon";

interface Props {
  selectedCount: number;
  loading: boolean;
  onSummarize: () => void;
  onRoadmap: () => void;
}

/** Actions on retrieved memories. Enabled once memories are selected. */
export function ActionPanel({ selectedCount, loading, onSummarize, onRoadmap }: Props) {
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
          <button className="action-btn" onClick={onSummarize} disabled={disabled}>
            <span className="action-emoji">📋</span> Extract key points
          </button>
          <button className="action-btn" disabled>
            <span className="action-emoji">🔗</span> Related memories
          </button>
        </div>
      </div>
    </div>
  );
}
