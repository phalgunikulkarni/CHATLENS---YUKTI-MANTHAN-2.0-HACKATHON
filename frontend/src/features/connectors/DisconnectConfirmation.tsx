import { useRef } from "react";
import { CONNECTOR_META } from "../../api/ConnectorService";
import type { ConnectorType } from "../../api/types";
import { useFocusTrap } from "../../hooks";
import { Icon } from "../../components/Icon";

/** Confirmation before disconnecting a source. Never deletes external data. */
export function DisconnectConfirmation({
  type,
  busy,
  onConfirm,
  onCancel,
}: {
  type: ConnectorType;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, true, onCancel);
  const meta = CONNECTOR_META[type];

  return (
    <div className="dialog-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onCancel(); }}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="disconnect-title" ref={ref} style={{ maxWidth: 440 }}>
        <div className="dialog-head">
          <div className="section-title" id="disconnect-title" style={{ marginBottom: 0, display: "flex", alignItems: "center", gap: 8 }}>
            <Icon name="close" size={18} style={{ color: "#ef4444" }} /> Disconnect {meta.name}?
          </div>
          <p className="card-desc" style={{ marginTop: 10 }}>
            ChatLens will stop accessing new memories from {meta.name}. Your data on {meta.name} is not deleted.
          </p>
        </div>
        <div className="dialog-foot">
          <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" style={{ background: "#ef4444" }} onClick={onConfirm} disabled={busy}>
            <Icon name="check" size={15} /> Disconnect
          </button>
        </div>
      </div>
    </div>
  );
}