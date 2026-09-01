import type { Connector } from "../../api/types";
import { Icon } from "../../components/Icon";
import { formatRelative } from "../../utils/format";
import { hasNumber } from "../../utils/guards";

/** A status label + dot. Sync details only render when the backend supplies them. */
export function ConnectorStatusView({ connector }: { connector: Connector }) {
  const { status, syncStatus, lastSyncedAt, indexedCount, syncProgress, error } = connector;

  if (status === "connecting") {
    return <span className="conn-status connecting"><span className="conn-dot" /> Connecting...</span>;
  }
  if (status === "error") {
    return <span className="conn-status error"><Icon name="wifi-off" size={13} /> {error ?? "Connection error"}</span>;
  }
  if (status === "not_connected") {
    return <span className="conn-status muted"><span className="conn-dot" /> Not connected</span>;
  }

  // status === "connected"
  const syncing = syncStatus === "syncing";
  return (
    <div>
      <span className="conn-status connected">
        <Icon name="check" size={13} /> Connected
      </span>
      {syncing && (
        <div style={{ marginTop: 8 }}>
          <span className="conn-status connecting"><span className="conn-dot" /> Syncing your memories...</span>
          {hasNumber(syncProgress) && (
            <div className="progress" style={{ marginTop: 6 }}><span style={{ width: `${syncProgress}%` }} /></div>
          )}
        </div>
      )}
      {syncStatus === "paused" && <div className="conn-sub">Sync paused</div>}
      {syncStatus === "error" && <div className="conn-sub" style={{ color: "#ef4444" }}>{error ?? "Sync error"}</div>}
      {/* Only show counts/timestamps the backend actually reported. */}
      {hasNumber(indexedCount) && <div className="conn-sub">{indexedCount} memories indexed</div>}
      {lastSyncedAt && <div className="conn-sub">Last synced {formatRelative(new Date(lastSyncedAt).getTime())}</div>}
    </div>
  );
}