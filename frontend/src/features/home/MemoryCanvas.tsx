import { Icon, type IconName } from "../../components/Icon";

interface Floater {
  icon: IconName;
  label: string;
  className: string;
}

/**
 * Subtle floating labels representing the CONTENT TYPES ChatLens can remember.
 * These are decorative structure only - not fabricated memories or queries, and
 * they carry no user data. Respects prefers-reduced-motion via CSS; hidden on
 * mobile.
 */
const FLOATERS: Floater[] = [
  { icon: "image", label: "Screenshots", className: "f1" },
  { icon: "text", label: "Notes", className: "f2" },
  { icon: "database", label: "Receipts", className: "f3" },
  { icon: "shapes", label: "Diagrams", className: "f4" },
  { icon: "layers", label: "Slides", className: "f5" },
  { icon: "brain", label: "Documents", className: "f6" },
];

export function MemoryCanvas() {
  return (
    <div className="memory-canvas" aria-hidden="true">
      {FLOATERS.map((f) => (
        <span key={f.label} className={`floater ${f.className}`} title={f.label}>
          <Icon name={f.icon} size={18} />
          <span>{f.label}</span>
        </span>
      ))}
    </div>
  );
}