import type { SearchResult, SummaryResponse } from "../../api/types";
import { Icon } from "../../components/Icon";

interface Props {
  summary: SummaryResponse;
  /** The currently loaded results, used to resolve source thumbnails. */
  resultItems: SearchResult[];
  onRoadmap: () => void;
}

export function SummaryPanel({ summary, resultItems, onRoadmap }: Props) {
  const sources = summary.usedImageIds
    .map((id) => resultItems.find((m) => m.id === id))
    .filter((r): r is SearchResult => Boolean(r))
    .slice(0, 4);

  return (
    <div className="panel">
      <div className="panel-head">
        <Icon name="summary" size={18} style={{ color: "var(--accent)" }} />
        <h3>AI Summary</h3>
      </div>
      <div className="panel-body">
        <p className="card-desc" style={{ marginBottom: 12 }}>{summary.summary}</p>
        {summary.points && summary.points.length > 0 && (
          <ul className="summary-points">
            {summary.points.map((p) => (
              <li key={p}><span className="bullet"><Icon name="check" size={16} /></span>{p}</li>
            ))}
          </ul>
        )}
        {sources.length > 0 && (
          <div className="source-thumbs" aria-label="Source memories">
            {sources.map((s) => (
              <img key={s.id} src={s.thumbnailUrl} alt={s.title ?? "Source memory"} />
            ))}
          </div>
        )}
        <button className="btn btn-primary" style={{ marginTop: 16, width: "100%" }} onClick={onRoadmap}>
          <Icon name="map" size={16} /> Create Revision Roadmap
        </button>
      </div>
    </div>
  );
}