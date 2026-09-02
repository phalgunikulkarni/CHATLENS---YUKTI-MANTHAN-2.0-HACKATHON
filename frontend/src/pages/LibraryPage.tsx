import { useMemo, useState } from "react";
import { useDispatch, useIngestion } from "../hooks";
import type { ConnectorMemorySource, SearchResult } from "../api/types";
import { MemoryGrid } from "../features/results/MemoryGrid";
import { SourceFilter, type SourceFilterValue } from "../features/results/SourceFilter";
import { EmptyState } from "../components/States";
import { Icon } from "../components/Icon";

/**
 * The library shows ONLY what the user actually added this session (their valid
 * uploads). No demo/fake memories. When the backend is connected it will supply
 * the persisted library (including connector-sourced memories); until then this
 * reflects real in-session uploads, tagged with the "uploaded" source.
 */
export function LibraryPage() {
  const { queue } = useIngestion();
  const dispatch = useDispatch();
  const [q, setQ] = useState("");
  const [source, setSource] = useState<SourceFilterValue>("all");

  const uploaded: SearchResult[] = useMemo(
    () =>
      queue
        .filter((it) => it.validation.valid)
        .map((it) => ({
          id: it.id,
          thumbnailUrl: it.previewUrl,
          fullUrl: it.previewUrl,
          title: it.fileName,
          sourceTag: "Uploaded this session",
          memorySource: "uploaded" as ConnectorMemorySource,
          // No OCR/score/metadata/explanation invented - those come from the backend.
        })),
    [queue]
  );

  const availableSources = useMemo(() => {
    const set = new Set<ConnectorMemorySource>();
    uploaded.forEach((m) => { if (m.memorySource) set.add(m.memorySource); });
    return [...set];
  }, [uploaded]);

  const items = useMemo(
    () =>
      uploaded.filter((m) => {
        const qOk = q.trim() === "" || (m.title ?? "").toLowerCase().includes(q.toLowerCase());
        const sOk = source === "all" || m.memorySource === source;
        return qOk && sOk;
      }),
    [uploaded, q, source]
  );

  if (uploaded.length === 0) {
    return (
      <EmptyState
        icon="library"
        title="Your visual memory starts here."
        message="Upload images to build your searchable visual archive."
        action={
          <button className="btn btn-primary" onClick={() => dispatch({ type: "VIEW_CHANGED", view: "upload" })}>
            <Icon name="upload" size={16} /> Upload images
          </button>
        }
      />
    );
  }

  return (
    <div>
      <div className="searchbar" style={{ boxShadow: "var(--shadow)", marginTop: 0, marginBottom: 18, maxWidth: 520 }}>
        <Icon name="search" size={20} className="search-icon" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search within your memories" aria-label="Search within memories" />
      </div>
      <SourceFilter available={availableSources} value={source} onChange={setSource} />
      <MemoryGrid
        results={items}
        selectedIds={[]}
        view="grid"
        onToggleSelect={() => {}}
        onOpen={() => {}}
        onWhy={() => {}}
      />
    </div>
  );
}