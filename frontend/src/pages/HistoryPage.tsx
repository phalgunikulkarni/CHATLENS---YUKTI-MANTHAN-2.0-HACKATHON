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
          <button
            className="history-item"
            key={h.id}
            onClick={() => rerun(h.query)}
            style={{ width: "100%", textAlign: "left", cursor: "pointer" }}
          >
            <div>
              <div className="history-q">{h.query}</div>
              <div className="history-meta">
                {formatRelative(h.at)} - {h.resultCount} {h.resultCount === 1 ? "result" : "results"}
              </div>
            </div>
            <span className="icon-btn" aria-hidden="true"><Icon name="arrow" size={16} /></span>
          </button>
        ))}
      </div>
    </div>
  );
}