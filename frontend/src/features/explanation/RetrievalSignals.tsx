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
 *
 * Phase 3D: when the Backend supplies a stored VLM (visual) description for the
 * image, it is shown as an additional "AI description" item INSIDE this same
 * section (as plain, unmodified text). It is optional evidence and never
 * replaces or alters the OCR / semantic / visual / metadata / clue signals.
 */
export function RetrievalSignals({
  signals,
  vlmDescription,
}: {
  signals: ExplanationSignal[] | undefined;
  vlmDescription?: string;
}) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  const hasSignals = hasItems(signals);
  const hasVlm = typeof vlmDescription === "string" && vlmDescription.trim().length > 0;

  if (!hasSignals && !hasVlm) {
    return <p className="explanation-empty">Explanation not available for this result.</p>;
  }

  return (
    <div>
      {hasSignals && (
        <>
          <div className="signal-chips">
            {signals!.map((s, i) => {
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

          {openIndex !== null && signals![openIndex] && (
            <div className="signal-expand" role="region">
              <div className="signal-expand-title">
                <Icon name="check" size={15} style={{ color: "#16a34a" }} />
                {signals![openIndex].label}
              </div>
              <p>{TYPE_EXPLANATION[signals![openIndex].type] ?? "This signal contributed to the result."}</p>
            </div>
          )}
        </>
      )}

      {hasVlm && (
        <div className="vlm-description" role="note">
          <div className="vlm-description-title">
            <Icon name="eye" size={15} style={{ color: "var(--accent)" }} />
            <span>AI description</span>
          </div>
          <p className="vlm-description-text">{vlmDescription!.trim()}</p>
        </div>
      )}
    </div>
  );
}