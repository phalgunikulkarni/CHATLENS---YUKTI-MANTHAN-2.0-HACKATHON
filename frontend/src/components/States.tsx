import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

export function EmptyState({
  icon = "search",
  title,
  message,
  action,
}: {
  icon?: IconName;
  title: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div className="state">
      <div className="state-icon"><Icon name={icon} size={30} /></div>
      <h3>{title}</h3>
      <p>{message}</p>
      {action}
    </div>
  );
}

export function ErrorState({ title, message, onRetry }: { title: string; message: string; onRetry?: () => void }) {
  return (
    <div className="state error-state" role="alert">
      <div className="state-icon"><Icon name="wifi-off" size={28} /></div>
      <h3>{title}</h3>
      <p>{message}</p>
      {onRetry && (
        <button className="btn btn-primary" onClick={onRetry}>Try again</button>
      )}
    </div>
  );
}

/**
 * Shown when an action needs the backend but none is connected. This is an
 * honest integration state - it never presents fabricated data as real.
 */
export function NotConnectedState({
  title = "Search service not connected yet",
  message = "Connect the ChatLens backend to retrieve your memories. Until then, results, explanations and summaries come from the live retrieval system.",
}: {
  title?: string;
  message?: string;
}) {
  return (
    <div className="state not-connected-state">
      <div className="state-icon" style={{ background: "rgba(79,140,255,0.12)", color: "var(--secondary)" }}>
        <Icon name="database" size={28} />
      </div>
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  );
}