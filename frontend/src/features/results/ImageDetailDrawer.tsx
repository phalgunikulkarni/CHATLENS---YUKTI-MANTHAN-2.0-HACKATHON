import { useEffect, useRef } from "react";
import type { SearchResult } from "../../api/types";
import { hasText } from "../../utils/guards";
import { deriveAltText } from "../../utils/altText";
import { formatDate } from "../../utils/format";
import { useFocusTrap } from "../../hooks";
import { Icon } from "../../components/Icon";
import { RetrievalSignals } from "../explanation/RetrievalSignals";
import { ImageChat } from "./ImageChat";

interface Props {
  result: SearchResult;
  selected: boolean;
  onClose: () => void;
  onToggleSelect: (id: string) => void;
  onSummarize: (id: string) => void;
  onRoadmap: (id: string) => void;
}

/** Full detail view. Renders only Backend-provided fields. Focus-trapped.
 *  Interactive: select, summarize, roadmap, and per-image conversational Q&A. */
export function ImageDetailDrawer({ result, selected, onClose, onToggleSelect, onSummarize, onRoadmap }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, true, onClose);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  const date = formatDate(result.capturedAt);
  const metaEntries = result.metadata ? Object.entries(result.metadata) : [];

  return (
    <div className="overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="drawer" role="dialog" aria-modal="true" aria-label="Memory details" ref={ref}>
        <div className="drawer-head">
          <span className="drawer-title">{hasText(result.title) ? result.title : "Memory"}</span>
          <button className="icon-btn" onClick={onClose} aria-label="Close details">
            <Icon name="close" size={18} />
          </button>
        </div>

        <img className="drawer-img" src={result.fullUrl ?? result.thumbnailUrl} alt={deriveAltText(result)} />

        <div className="drawer-section">
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            {hasText(result.sourceTag) && <span className="sig-tag">{result.sourceTag}</span>}
            {date && <span className="card-date">{date}</span>}
          </div>
          {hasText(result.description) && (
            <p className="card-desc" style={{ marginTop: 12 }}>{result.description}</p>
          )}

          <div className="drawer-actions">
            <button
              className={`btn ${selected ? "btn-primary" : "btn-ghost"}`}
              onClick={() => onToggleSelect(result.id)}
              aria-pressed={selected}
            >
              <Icon name="check" size={15} /> {selected ? "Selected" : "Select memory"}
            </button>
            <button className="btn btn-subtle" onClick={() => onSummarize(result.id)}>
              <Icon name="summary" size={15} /> Summarize
            </button>
            <button className="btn btn-subtle" onClick={() => onRoadmap(result.id)}>
              <Icon name="map" size={15} /> Roadmap
            </button>
          </div>
        </div>

        {hasText(result.ocrSnippet) && (
          <div className="drawer-section">
            <div className="section-title" style={{ fontSize: 12 }}>Extracted text (OCR)</div>
            <div className="ocr-box">{result.ocrSnippet}</div>
          </div>
        )}

        {metaEntries.length > 0 && (
          <div className="drawer-section">
            <div className="section-title" style={{ fontSize: 12 }}>Metadata</div>
            {metaEntries.map(([k, v]) => (
              <div className="kv" key={k}>
                <span className="k">{k}</span>
                <span className="v">{v}</span>
              </div>
            ))}
          </div>
        )}

        <div className="drawer-section">
          <div className="section-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Icon name="sparkles" size={16} style={{ color: "var(--accent)" }} /> Why this result?
          </div>
          <RetrievalSignals signals={result.explanation} />
        </div>

        <div className="drawer-section" style={{ borderBottom: "none" }}>
          <ImageChat imageId={result.id} />
        </div>
      </div>
    </div>
  );
}