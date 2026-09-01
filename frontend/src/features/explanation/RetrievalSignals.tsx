import { useState } from "react";
import type { ExplanationSignal, ExplanationSignalType } from "../../api/types";
import { hasItems, hasNumber } from "../../utils/guards";
import { IS_DEMO_MODE } from "../../api/client";
import { Icon, type IconName } from "../../components/Icon";

const ICON_MAP: Record<string, IconName> = {
  text: "text",
  brain: "brain",
  eye: "eye",
  shapes: "shapes",
  database: "database",
  tag: "tag",
};

/** Short human explanation for each signal type (shown when a chip is expanded). */
const TYPE_EXPLANATION: Record<ExplanationSignalType, string> = {
  ocr: "Matched text detected inside the image.",
  semantic: "Image meaning is related to the search query.",
  visual: "Visual features are similar to the requested memory.",
  metadata: "Date, source or category information supports the result.",
  clue: "A memory clue you provided matched this result.",
};

const TYPE_LABEL: Record<ExplanationSignalType, string> = {
  ocr: "OCR",
  semantic: "Semantic",
  visual: "Visual",
  metadata: "Metadata",
  clue: "Clue",
};

/**
 * Interactive retrieval explanation. Renders each Backend-provided signal as a
 * clickable chip (with its strength %) that expands a short explanation. Renders
 * only signals present in the payload and never fabricates evidence. In demo
 * mode the block is clearly labeled as demo data.
 */
export function RetrievalSignals({
  signals,
  matchScore,
}: {
  signals: ExplanationSignal[] | undefined;
  matchScore?: number;
}) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  if (!hasItems(signals)) {
    return <p className="explanation-empty">Explanation not available for this result.</p>;
  }

  return (
    <div>
      {IS_DEMO_MODE && <span className="demo-tag">Demo explanation</span>}

      <div className="signal-chips">
        {signals.map((s, i) => {
          const open = openIndex === i;
          const pct = hasNumber(s.strength) ? `${Math.round(s.strength * 100)}%` : null;
          return (
            <button
              key={`${s.type}-${i}`}
              className={`signal-chip ${open ? "open" : ""}`}
              aria-expanded={open}
              onClick={() => setOpenIndex(open ? null : i)}
            >
              <Icon name={ICON_MAP[s.icon] ?? "sparkles"} size={14} />
              <span>{TYPE_LABEL[s.type] ?? s.type}</span>
              {pct && <strong>{pct}</strong>}
            </button>
          );
        })}
      </div>

      {openIndex !== null && signals[openIndex] && (
        <div className="signal-expand" role="region">
          <div className="signal-expand-title">
            <Icon name="check" size={15} style={{ color: "#16a34a" }} />
            {signals[openIndex].label}
          </div>
          <p>{TYPE_EXPLANATION[signals[openIndex].type] ?? "This signal contributed to the result."}</p>
          {hasNumber(signals[openIndex].strength) && (
            <div className="bar" aria-hidden="true">
              <span style={{ width: `${Math.round((signals[openIndex].strength ?? 0) * 100)}%` }} />
            </div>
          )}
        </div>
      )}

      {hasNumber(matchScore) && (
        <p className="card-date" style={{ marginTop: 10 }}>
          Overall relevance {Math.round(matchScore * 100)}% (supporting context)
        </p>
      )}
    </div>
  );
}