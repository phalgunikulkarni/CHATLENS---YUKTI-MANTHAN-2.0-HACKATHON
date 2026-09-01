import { useRef, useState } from "react";
import type { Connector } from "../../api/types";
import { CONNECTOR_META } from "../../api/ConnectorService";
import { useFocusTrap } from "../../hooks";
import { Icon } from "../../components/Icon";
import { ConnectorStatusView } from "./ConnectorStatusView";

interface Props {
  connector: Connector;
  busy: boolean;
  onSync: () => void;
  onPause: () => void;
  onDisconnect: () => void;
  onClose: () => void;
}

/** Manage a connected source: sync, pause, view status, or disconnect. */
export function ManageConnectorModal({ connector, busy, onSync, onPause, onDisconnect, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, true, onClose);
  const meta = CONNECTOR_META[connector.type];
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);

  return (
    <div className="dialog-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="manage-title" ref={ref}>
        <div className="dialog-head">
          <div className="section-title" id="manage-title" style={{ marginBottom: 0 }}>Manage {meta.name}</div>
          <div style={{ marginTop: 12 }}><ConnectorStatusView connector={connector} /></div>
        </div>

        <div className="dialog-body">
          {!confirmDisconnect ? (
            <div className="manage-actions">
              <button className="btn btn-subtle" onClick={onSync} disabled={busy}>
                <Icon name="history" size={15} /> Sync now
              </button>
              <button className="btn btn-ghost" onClick={onPause} disabled={busy}>
                <Icon name="close" size={15} /> Pause sync
              </button>
            </div>
          ) : (
            <div className="state error-state" style={{ padding: "18px 8px" }}>
              <h3>Disconnect {meta.name}?</h3>
              <p>This will stop ChatLens from accessing new memories from {meta.name}. Your data on {meta.name}
              {" "}is not deleted.</p>
            </div>
          )}
        </div>

        <div className="dialog-foot">
          {!confirmDisconnect ? (
            <>
              <button className="btn btn-ghost" onClick={onClose}>Close</button>
              <button className="btn btn-ghost" style={{ color: "#ef4444", borderColor: "#f3c2c2" }} onClick={() => setConfirmDisconnect(true)}>
                Disconnect
              </button>
            </>
          ) : (
            <>
              <button className="btn btn-ghost" onClick={() => setConfirmDisconnect(false)}>Cancel</button>
              <button className="btn btn-primary" style={{ background: "#ef4444" }} onClick={onDisconnect} disabled={busy}>
                <Icon name="check" size={15} /> Disconnect
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}