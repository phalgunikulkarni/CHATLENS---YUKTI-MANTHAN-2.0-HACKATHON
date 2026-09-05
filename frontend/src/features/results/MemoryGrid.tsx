import type { SearchResult } from "../../api/types";
import { MemoryCard } from "./MemoryCard";

interface Props {
  results: SearchResult[];
  selectedIds: string[];
  view: "grid" | "list";
  onToggleSelect: (id: string) => void;
  onOpen: (id: string) => void;
  onWhy: (id: string) => void;
  /** Forwarded to each card. True only for Search Results (not the Library). */
  showRetrievalExplanation?: boolean;
}

export function MemoryGrid({
  results,
  selectedIds,
  view,
  onToggleSelect,
  onOpen,
  onWhy,
  showRetrievalExplanation = false,
}: Props) {
  return (
    <div className={`grid ${view === "list" ? "list" : ""}`}>
      {results.map((r) => (
        <MemoryCard
          key={r.id}
          result={r}
          view={view}
          selected={selectedIds.includes(r.id)}
          onToggleSelect={onToggleSelect}
          onOpen={onOpen}
          onWhy={onWhy}
          showRetrievalExplanation={showRetrievalExplanation}
        />
      ))}
    </div>
  );
}