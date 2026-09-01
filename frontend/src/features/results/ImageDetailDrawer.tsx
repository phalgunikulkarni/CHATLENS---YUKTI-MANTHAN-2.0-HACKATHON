import { useEffect, useRef } from "react";
import type { SearchResult } from "../../api/types";
import { hasNumber, hasText } from "../../utils/guards";
import { deriveAltText } from "../../utils/altText";
import { formatDate, formatScore } from "../../utils/format";
import { useFocusTrap } from "../../hooks";
import { Icon } from "../../components/Icon";
import { RetrievalSignals } from "../explanation/RetrievalSignals";

interface Props {
  result: SearchResult;
  onClose: () => void;
}

/** Full detail view. Renders only Backend-provided fields. Focus-trapped. */
export function ImageDetailDrawer({ result, onClose }: Props) {
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
            {hasNumber(result.matchScore) && (
              <span className="score-badge" style={{ position: "static", background: "var(--navy)" }}>
                {formatScore(result.matchScore)} Match
              </span>
            )}
            {hasText(result.sourceTag) && <span className="sig-tag">{result.sourceTag}</span>}
            {date && <span className="card-date">{date}</span>}
          </div>
          {hasText(result.description) && (
            <p className="card-desc" style={{ marginTop: 12 }}>{result.description}</p>
          )}
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

        <div className="drawer-section" style={{ borderBottom: "none" }}>
          <div className="section-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Icon name="sparkles" size={16} style={{ color: "var(--accent)" }} /> Why this result?
          </div>
          <RetrievalSignals signals={result.explanation} matchScore={result.matchScore} />
        </div>
      </div>
    </div>
  );
}
