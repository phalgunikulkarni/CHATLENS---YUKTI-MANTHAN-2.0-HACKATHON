import { Icon } from "../../components/Icon";

/** Honest connection-failure state. Never shows a connected status on failure. */
export function ConnectionError({ onRetry, onCancel }: { onRetry: () => void; onCancel: () => void }) {
  return (
    <div className="state error-state" role="alert" style={{ padding: "24px 12px" }}>
      <div className="state-icon"><Icon name="wifi-off" size={26} /></div>
      <h3>Unable to connect</h3>
      <p>ChatLens couldn&apos;t establish a connection right now. Please try again.</p>
      <div style={{ display: "flex", gap: 10, justifyContent: "center", marginTop: 8 }}>
        <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
        <button className="btn btn-primary" onClick={onRetry}><Icon name="history" size={15} /> Retry</button>
      </div>
    </div>
  );
}