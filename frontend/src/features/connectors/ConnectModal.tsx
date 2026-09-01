import { useRef } from "react";
import type { Connector } from "../../api/types";
import { CONNECTOR_META } from "../../api/ConnectorService";
import { IS_BACKEND_CONNECTED } from "../../api/client";
import { useFocusTrap } from "../../hooks";
import { Icon } from "../../components/Icon";
import { ConnectorLogo } from "./ConnectorLogo";

interface Props {
  connector: Connector;
  busy: boolean;
  onContinue: () => void;
  onCancel: () => void;
}

/**
 * Confirmation before connecting a source. Because real auth may not exist yet,
 * when no backend is connected this clearly states "integration coming soon"
 * and never simulates a successful OAuth login.
 */
export function ConnectModal({ connector, busy, onContinue, onCancel }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, true, onCancel);
  const meta = CONNECTOR_META[connector.type];

  return (
    <div className="dialog-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onCancel(); }}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="connect-title" ref={ref}>
        <div className="dialog-head">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <ConnectorLogo type={connector.type} size={44} />
            <div className="section-title" id="connect-title" style={{ marginBottom: 0 }}>
              Connect {meta.name} to ChatLens?
            </div>
          </div>
          <p className="card-desc" style={{ marginTop: 12 }}>
            ChatLens will use this connection to discover and index your visual memories from {meta.name}
            so you can search them in natural language. Permissions are managed by the sign-in and backend
            system, and you can disconnect at any time.
          </p>
        </div>

        {!IS_BACKEND_CONNECTED && (
          <div className="dialog-body">
            <div className="state not-connected-state" style={{ padding: "22px 16px" }}>
              <div className="state-icon" style={{ background: "rgba(124,92,252,0.12)", color: "var(--accent)" }}>
                <Icon name="sparkles" size={26} />
              </div>
              <h3>Integration coming soon</h3>
              <p>Your backend connector will be connected here. ChatLens will not sign you in or access
              {" "}{meta.name} until the real integration is available.</p>
            </div>
          </div>
        )}

        <div className="dialog-foot">
          <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" onClick={onContinue} disabled={busy}>
            <Icon name="arrow" size={15} /> Continue
          </button>
        </div>
      </div>
    </div>
  );
}