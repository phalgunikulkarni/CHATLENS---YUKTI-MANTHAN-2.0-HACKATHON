import type { MemoryClue } from "../../api/types";
import { Icon } from "../../components/Icon";

interface Props {
  query: string;
  count: number;
  clues: MemoryClue[];
  view: "grid" | "list";
  refining: boolean;
  onRemoveClue: (id: string) => void;
  onToggleView: (v: "grid" | "list") => void;
}

export function ResultsHeader({ query, count, clues, view, refining, onRemoveClue, onToggleView }: Props) {
  return (
    <div>
      <div className="results-head">
        <div>
          <h2>Results for "{query}"</h2>
          <p className="results-meta">
            {count} {count === 1 ? "memory" : "memories"} found
            {refining && " - refining..."}
          </p>
        </div>
        <div className="toolbar">
          <div className="toggle-group" role="group" aria-label="View mode">
            <button className={view === "grid" ? "active" : ""} onClick={() => onToggleView("grid")} aria-label="Grid view" aria-pressed={view === "grid"}>
              <Icon name="grid" size={16} />
            </button>
            <button className={view === "list" ? "active" : ""} onClick={() => onToggleView("list")} aria-label="List view" aria-pressed={view === "list"}>
              <Icon name="list" size={16} />
            </button>
          </div>
        </div>
      </div>
      {clues.length > 0 && (
        <div className="clue-row" aria-label="Active memory clues">
          <span style={{ fontSize: 12.5, fontWeight: 700, color: "var(--muted)" }}>Clues:</span>
          {clues.map((c) => (
            <span className="clue-pill" key={c.id}>
              <Icon name="tag" size={13} /> {c.label}
              <button onClick={() => onRemoveClue(c.id)} aria-label={`Remove clue ${c.label}`}>
                <Icon name="close" size={13} />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
