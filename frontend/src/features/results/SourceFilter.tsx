import type { ConnectorMemorySource } from "../../api/types";
import { SOURCE_LABEL } from "../../utils/format";

export type SourceFilterValue = ConnectorMemorySource | "all";

interface Props {
  /** Sources actually present in the current data set (backend/session only). */
  available: ConnectorMemorySource[];
  value: SourceFilterValue;
  onChange: (v: SourceFilterValue) => void;
}

/**
 * Source filter chips. Only renders "All" plus the sources that are actually
 * present in the current results/library - it never invents source options.
 */
export function SourceFilter({ available, value, onChange }: Props) {
  if (available.length === 0) return null;
  const options: SourceFilterValue[] = ["all", ...available];
  return (
    <div className="source-filter" role="group" aria-label="Filter by source">
      {options.map((opt) => (
        <button
          key={opt}
          className={`cat-tab ${value === opt ? "active" : ""}`}
          aria-pressed={value === opt}
          onClick={() => onChange(opt)}
        >
          {opt === "all" ? "All sources" : SOURCE_LABEL[opt] ?? opt}
        </button>
      ))}
    </div>
  );
}