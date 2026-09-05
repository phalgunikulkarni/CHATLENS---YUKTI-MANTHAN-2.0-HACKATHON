import { Icon } from "../../components/Icon";
import { SOURCE_LABEL } from "../../utils/format";
import type { SearchResult } from "../../api/types";
import { pillForResult } from "./ResultsToolbar";

/**
 * Quick Insights: small summary derived ONLY from the real current results
 * (counts by type + by source). No fabricated data; hidden when there are no
 * results to describe.
 */
export function QuickInsights({ results }: { results: SearchResult[] }) {
  if (results.length === 0) return null;

  const byType = new Map<string, number>();
  const bySource = new Map<string, number>();
  for (const r of results) {
    const t = pillForResult(r);
    if (t) byType.set(t, (byType.get(t) ?? 0) + 1);
    if (r.memorySource) {
      const s = SOURCE_LABEL[r.memorySource] ?? r.memorySource;
      bySource.set(s, (bySource.get(s) ?? 0) + 1);
    }
  }
  const topType = [...byType.entries()].sort((a, b) => b[1] - a[1])[0];

  return (
    <div className="panel cl-insights">
      <div className="panel-head">
        <Icon name="eye" size={18} style={{ color: "var(--accent)" }} />
        <h3>Quick Insights</h3>
      </div>
      <div className="panel-body cl-insights-body">
        <div className="cl-insight-row"><span>Total memories</span><strong>{results.length}</strong></div>
        {topType && <div className="cl-insight-row"><span>Most common</span><strong>{topType[0]} ({topType[1]})</strong></div>}
        {byType.size > 0 && (
          <div className="cl-insight-tags">
            {[...byType.entries()].map(([t, n]) => (
              <span key={t} className="cl-insight-tag">{t} · {n}</span>
            ))}
          </div>
        )}
        {bySource.size > 0 && (
          <div className="cl-insight-sources">
            {[...bySource.entries()].map(([s, n]) => (
              <span key={s} className="cl-insight-src">{s} · {n}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
