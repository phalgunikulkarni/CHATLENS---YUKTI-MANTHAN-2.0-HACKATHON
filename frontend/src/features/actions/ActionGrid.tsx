import { Icon, type IconName } from "../../components/Icon";

export type ActionId =
  | "summarize" | "roadmap" | "key_points" | "related"
  | "add_calendar" | "add_task" | "research" | "analyze_bill";

export interface ActionDef { id: ActionId; label: string; icon: IconName; }

/** The single canonical list of the 8 actions (same order everywhere). */
export const ACTIONS: ActionDef[] = [
  { id: "summarize", label: "Summarize", icon: "summary" },
  { id: "roadmap", label: "Revision Roadmap", icon: "map" },
  { id: "key_points", label: "Extract Key Points", icon: "list" },
  { id: "related", label: "Related Memories", icon: "layers" },
  { id: "add_calendar", label: "Add to Calendar", icon: "calendar" },
  { id: "add_task", label: "Add Task", icon: "tasks" },
  { id: "research", label: "Research", icon: "brain" },
  { id: "analyze_bill", label: "Analyze Bill", icon: "tag" },
];

/** Single shared specular action button — identical style for all 8 actions. */
export function ActionButton({ def, onClick, disabled }: { def: ActionDef; onClick: () => void; disabled?: boolean }) {
  return (
    <button className="cl-action" onClick={onClick} disabled={disabled} aria-label={def.label}>
      <span className="cl-action-glow" aria-hidden="true" />
      <span className="cl-action-icon"><Icon name={def.icon} size={18} /></span>
      <span className="cl-action-label">{def.label}</span>
    </button>
  );
}

/** Unified action section: heading + all 8 actions in one grid. */
export function ActionGrid({
  heading,
  onAction,
  disabledIds,
}: {
  heading: string;
  onAction: (id: ActionId) => void;
  disabledIds?: Partial<Record<ActionId, boolean>>;
}) {
  return (
    <section className="cl-action-section">
      <h2 className="cl-action-heading">{heading}</h2>
      <div className="cl-action-grid">
        {ACTIONS.map((def) => (
          <ActionButton key={def.id} def={def} onClick={() => onAction(def.id)} disabled={disabledIds?.[def.id]} />
        ))}
      </div>
    </section>
  );
}
