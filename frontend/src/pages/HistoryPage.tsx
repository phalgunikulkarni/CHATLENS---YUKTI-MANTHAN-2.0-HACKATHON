import { useDispatch, useUi } from "../hooks";
import { useChatLens } from "../hooks/useChatLens";
import { formatRelative } from "../utils/format";
import { Icon } from "../components/Icon";
import { EmptyState } from "../components/States";

export function HistoryPage() {
  const { searchHistory } = useUi();
  const c = useChatLens();
  const dispatch = useDispatch();

  const rerun = (query: string) => {
    dispatch({ type: "VIEW_CHANGED", view: "search" });
    c.runSearch(query);
  };

  if (searchHistory.length === 0) {
    return (
      <EmptyState
        icon="history"
        title="No searches yet"
        message="Your searches will appear here once you start searching."
      />
    );
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div className="section-title" style={{ marginBottom: 0 }}>Recent searches</div>
        <button className="btn btn-subtle" onClick={c.clearHistory}>Clear history</button>
      </div>
      <div style={{ marginTop: 14 }}>
        {searchHistory.map((h) => (
          <div className="history-item" key={h.id}>
            <button
              className="history-main"
              onClick={() => rerun(h.query)}
              style={{ background: "none", border: "none", textAlign: "left", cursor: "pointer", flex: 1, minWidth: 0 }}
              aria-label={`Search again: ${h.query}`}
            >
              <div className="history-q">{h.query}</div>
              <div className="history-meta">
                {formatRelative(h.at)} - {h.resultCount} {h.resultCount === 1 ? "result" : "results"}
              </div>
            </button>
            <div className="history-item-actions">
              <button className="btn btn-subtle" onClick={() => rerun(h.query)}>
                <Icon name="search" size={14} /> Search again
              </button>
              <button className="icon-btn" aria-label={`Delete search: ${h.query}`} onClick={() => c.removeHistoryItem(h.id)}>
                <Icon name="close" size={16} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}