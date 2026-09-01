import { Icon, type IconName } from "../../components/Icon";

interface Floater {
  icon: IconName;
  label: string;
  query: string;
  className: string;
}

/** Subtle floating elements representing the content types ChatLens remembers.
 *  Decorative but interactive; respects prefers-reduced-motion via CSS. */
const FLOATERS: Floater[] = [
  { icon: "image", label: "Screenshots", query: "Find my Python login error", className: "f1" },
  { icon: "text", label: "Notes", query: "Find my CN notes about OSI", className: "f2" },
  { icon: "database", label: "Receipts", query: "Find the receipt around INR 800", className: "f3" },
  { icon: "shapes", label: "Diagrams", query: "Find my project architecture diagram", className: "f4" },
  { icon: "layers", label: "Slides", query: "Find my lecture slides", className: "f5" },
  { icon: "brain", label: "Code", query: "Find my Python code screenshots", className: "f6" },
];

export function MemoryCanvas({ onPick }: { onPick: (query: string) => void }) {
  return (
    <div className="memory-canvas" aria-hidden="false">
      {FLOATERS.map((f) => (
        <button
          key={f.label}
          className={`floater ${f.className}`}
          onClick={() => onPick(f.query)}
          aria-label={`Search ${f.label}`}
          title={f.label}
        >
          <Icon name={f.icon} size={18} />
          <span>{f.label}</span>
        </button>
      ))}
    </div>
  );
}