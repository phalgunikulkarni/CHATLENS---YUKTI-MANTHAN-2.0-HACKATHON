import type { ExplanationSignal } from "../../api/types";
import { hasItems, hasNumber } from "../../utils/guards";
import { Icon, type IconName } from "../../components/Icon";

const ICON_MAP: Record<string, IconName> = {
  text: "text",
  brain: "brain",
  eye: "eye",
  shapes: "shapes",
  database: "database",
  tag: "tag",
};

/**
 * Renders exactly the Backend-provided explanation signals as icon+text rows,
 * with an optional strength bar. Never fabricates; shows an honest empty state
 * when there are no signals.
 */
export function RetrievalSignals({
  signals,
  matchScore,
}: {
  signals: ExplanationSignal[] | undefined;
  matchScore?: number;
}) {
  if (!hasItems(signals)) {
    return <p className="explanation-empty">Explanation not available for this result.</p>;
  }
  return (
    <div>
      {signals.map((s, i) => (
        <div className="signal" key={`${s.type}-${i}`}>
          <div className="signal-top">
            <Icon name="check" size={16} style={{ color: "#16a34a" }} />
            <Icon name={ICON_MAP[s.icon] ?? "sparkles"} size={16} style={{ color: "var(--accent)" }} />
            <span>{s.label}</span>
          </div>
          {hasNumber(s.strength) && (
            <div className="bar" aria-hidden="true">
              <span style={{ width: `${Math.round(s.strength * 100)}%` }} />
            </div>
          )}
        </div>
      ))}
      {hasNumber(matchScore) && (
        <p className="card-date" style={{ marginTop: 4 }}>
          Overall relevance {Math.round(matchScore * 100)}% (supporting context)
        </p>
      )}
    </div>
  );
}
