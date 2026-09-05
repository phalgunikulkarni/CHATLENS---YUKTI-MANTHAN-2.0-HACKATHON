import { useState } from "react";
import { Icon } from "../../components/Icon";
import { isSendable } from "../../utils/validation";
import type { SearchResult } from "../../api/types";

export type SortValue = "relevance" | "recent";

/** Category filter values shown as pills (only those present in real results). */
export type CategoryValue = "all" | string;

interface Props {
  query: string;
  count: number;
  results: SearchResult[];
  category: CategoryValue;
  sort: SortValue;
  onSearch: (q: string) => void;
  onCategory: (c: CategoryValue) => void;
  onSort: (s: SortValue) => void;
}

// Reference pill order; we only render a pill when that category exists in the
// current results (plus a couple of common labels mapped from result.category).
const PILL_ORDER = ["Photos", "Documents", "Receipts", "Videos", "Notes"];

function categoryLabel(raw: string): string {
  const c = raw.toLowerCase();
  if (c.includes("receipt") || c.includes("reciept")) return "Receipts";  // dataset spells it "Reciepts"
  if (c.includes("note")) return "Notes";
  if (c.includes("video")) return "Videos";
  if (c.includes("doc") || c.includes("slide") || c.includes("pdf")) return "Documents";
  if (c.includes("photo") || c.includes("image") || c.includes("meme") || c.includes("screenshot")) return "Photos";
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

/** Map a result to its display pill label (used for filtering + counts). */
export function pillForResult(r: SearchResult): string | null {
  return r.category ? categoryLabel(r.category) : null;
}

/**
 * Top results toolbar: a persistent full-width search bar (query stays visible
 * and editable), real-data category pills, a sort control, and the result
 * count line. Purely presentational + existing search wiring — no fabrication.
 */
export function ResultsToolbar({ query, count, results, category, sort, onSearch, onCategory, onSort }: Props) {
  const [draft, setDraft] = useState(query);

  // Only pills for categories actually present in the results.
  const present = new Set<string>();
  results.forEach((r) => { const p = pillForResult(r); if (p) present.add(p); });
  const ordered = PILL_ORDER.filter((p) => present.has(p));
  const extras = [...present].filter((p) => !PILL_ORDER.includes(p)).sort();
  const pills: CategoryValue[] = ["all", ...ordered, ...extras];

  const submit = () => { if (isSendable(draft)) onSearch(draft.trim()); };

  return (
    <div className="cl-results-toolbar">
      <div className="cl-searchbar">
        <Icon name="search" size={20} className="search-icon" />
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
          placeholder="Search your memories…"
          aria-label="Search your memories"
        />
        <button className="cl-search-go" onClick={submit} disabled={!isSendable(draft)} aria-label="Search">
          <Icon name="arrow" size={18} />
        </button>
      </div>

      <div className="cl-results-controls">
        <div className="cl-pills" role="group" aria-label="Filter by type">
          {pills.map((p) => (
            <button
              key={p}
              className={`cl-pill ${category === p ? "active" : ""}`}
              aria-pressed={category === p}
              onClick={() => onCategory(p)}
            >
              {p === "all" ? "All" : p}
            </button>
          ))}
        </div>
        <label className="cl-sort">
          <span>Sort</span>
          <select value={sort} onChange={(e) => onSort(e.target.value as SortValue)} aria-label="Sort results">
            <option value="relevance">Relevance</option>
            <option value="recent">Most recent</option>
          </select>
        </label>
      </div>

      <p className="cl-result-count">
        Found <strong>{count}</strong> {count === 1 ? "result" : "results"}
        {query ? <> for "<span className="cl-q">{query}</span>"</> : null}
      </p>
    </div>
  );
}
