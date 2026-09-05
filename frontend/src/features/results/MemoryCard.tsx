import type { SearchResult } from "../../api/types";
import { hasText } from "../../utils/guards";
import { deriveAltText } from "../../utils/altText";
import { formatDate, CATEGORY_LABEL } from "../../utils/format";
import { Icon } from "../../components/Icon";
import { SourceBadge } from "../../components/SourceBadge";
import { ProtectedImage } from "../../components/ProtectedImage";

interface Props {
  result: SearchResult;
  selected: boolean;
  view: "grid" | "list";
  onToggleSelect: (id: string) => void;
  onOpen: (id: string) => void;
  onWhy: (id: string) => void;
}

/** A memory result card. Renders ONLY fields present in the payload. */
export function MemoryCard({ result, selected, view, onToggleSelect, onOpen, onWhy }: Props) {
  const date = formatDate(result.capturedAt);
  return (
    <div className={`card ${view === "list" ? "list" : ""} ${selected ? "selected" : ""}`}>
      <button
        className="card-thumb"
        onClick={() => onToggleSelect(result.id)}
        aria-pressed={selected}
        aria-label={selected ? "Deselect memory" : "Select memory"}
        style={{ border: "none", padding: 0, cursor: "pointer" }}
      >
        <ProtectedImage src={result.thumbnailUrl} alt={deriveAltText(result)} loading="lazy" />
        <span className="select-tick"><Icon name="check" size={16} /></span>
      </button>
      <div className="card-body">
        {hasText(result.category) && (
          <span className="card-cat">{CATEGORY_LABEL[result.category] ?? result.category}</span>
        )}
        {hasText(result.title) && (
          <button
            className="card-title"
            onClick={() => onOpen(result.id)}
            style={{ background: "none", border: "none", padding: 0, textAlign: "left", cursor: "pointer" }}
          >
            {result.title}
          </button>
        )}
        {hasText(result.description) && <p className="card-desc">{result.description}</p>}
        {result.memorySource && (
          <div style={{ marginTop: 2 }}><SourceBadge source={result.memorySource} /></div>
        )}
        {result.explanation && result.explanation.length > 0 && (
          <div className="signal-mini">
            {[...new Set(result.explanation.map((s) => s.type))].slice(0, 4).map((t) => (
              <span className="sig-tag" key={t}>
                <Icon name="check" size={11} /> {t.toUpperCase()}
              </span>
            ))}
          </div>
        )}
        <div className="card-foot">
          <button className="why-link" onClick={() => onWhy(result.id)}>
            <Icon name="sparkles" size={14} /> Why this result?
          </button>
          {date && <span className="card-date">{date}</span>}
        </div>
      </div>
    </div>
  );
}