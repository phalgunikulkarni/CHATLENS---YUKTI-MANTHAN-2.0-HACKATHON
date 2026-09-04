import { useState } from "react";
import type { ExplanationSignal, ExplanationSignalType } from "../../api/types";
import { hasItems } from "../../utils/guards";
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
 * clickable chip (icon + type label) that expands a short grounded explanation.
 * Renders only signals present in the payload and never fabricates evidence.
 * No retrieval percentages are shown to the user.
 */
export function RetrievalSignals({
  signals,
}: {
  signals: ExplanationSignal[] | undefined;
}) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  if (!hasItems(signals)) {
    return <p className="explanation-empty">Explanation not available for this result.</p>;
  }

  return (
    <div>
      <div className="signal-chips">
        {signals.map((s, i) => {
          const open = openIndex === i;
          return (
            <button
              key={`${s.type}-${i}`}
              className={`signal-chip ${open ? "open" : ""}`}
              aria-expanded={open}
              onClick={() => setOpenIndex(open ? null : i)}
            >
              <Icon name={ICON_MAP[s.icon] ?? "sparkles"} size={14} />
              <span>{TYPE_LABEL[s.type] ?? s.type}</span>
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
        </div>
      )}
    </div>
  );
}