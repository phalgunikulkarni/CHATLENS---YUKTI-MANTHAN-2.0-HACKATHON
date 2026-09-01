import { useState } from "react";
import { Icon, type IconName } from "../../components/Icon";

interface Mode {
  key: string;
  label: string;
  icon: IconName;
  explanation: string;
}

/** These communicate ChatLens's multimodal nature. They are explanatory only -
 *  they do NOT claim to change backend ranking. */
const MODES: Mode[] = [
  { key: "ocr", label: "OCR", icon: "text", explanation: "Understands text inside your images." },
  { key: "visual", label: "Visual", icon: "eye", explanation: "Understands what the image looks like." },
  { key: "semantic", label: "Semantic", icon: "brain", explanation: "Understands the meaning of your memory." },
  { key: "memory", label: "Memory", icon: "sparkles", explanation: "Combines clues to find the most relevant result." },
];

export function SearchModes() {
  const [open, setOpen] = useState<string | null>(null);
  const active = MODES.find((m) => m.key === open);
  return (
    <div className="search-modes">
      <div className="search-modes-row">
        {MODES.map((m) => (
          <button
            key={m.key}
            className={`mode-pill ${open === m.key ? "active" : ""}`}
            onClick={() => setOpen(open === m.key ? null : m.key)}
            aria-expanded={open === m.key}
          >
            <Icon name={m.icon} size={14} /> {m.label}
          </button>
        ))}
      </div>
      {active && (
        <p className="mode-explain" role="status">
          <strong>{active.label}:</strong> {active.explanation}
        </p>
      )}
    </div>
  );
}