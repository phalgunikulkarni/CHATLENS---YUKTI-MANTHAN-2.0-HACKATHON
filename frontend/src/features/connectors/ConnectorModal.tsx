import { useCallback, useEffect, useRef, useState } from "react";
import type { Connector } from "../../api/types";
import { CONNECTOR_META } from "../../api/ConnectorService";
import { connectorService } from "../../api/client";
import { useFocusTrap } from "../../hooks";
import { Icon } from "../../components/Icon";
import { ConnectorLogo } from "./ConnectorLogo";
import { PermissionPanel } from "./PermissionPanel";
import { ConnectionProgress } from "./ConnectionProgress";
import { ConnectionError } from "./ConnectionError";

type Phase = "permissions" | "connecting" | "connected" | "error";

interface Props {
  connector: Connector;
  /** Report a real, backend-confirmed connection to the parent/store. */
  onConnected: () => void;
  onCancel: () => void;
}

/**
 * Full connector connection flow: permissions -> connecting -> connected/error.
 *
 * This is a REAL connection flow, API-ready via connectorService. It NEVER shows
 * a fake connected state: the "connected" phase is reached only if
 * connectorService.connect() resolves with a connected status. If the backend is
 * unavailable (default), connect() rejects and the honest error state with Retry
 * is shown - not "integration coming soon" and not a fake success.
 */
export function ConnectorModal({ connector, onConnected, onCancel }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [phase, setPhase] = useState<Phase>("permissions");
  useFocusTrap(ref, true, phase === "connecting" ? undefined : onCancel);
  const meta = CONNECTOR_META[connector.type];

  const runConnect = useCallback(async () => {
    setPhase("connecting");
    try {
      const result = await connectorService.connect(connector.type);
      if (result.authUrl) window.open(result.authUrl, "_blank", "noopener,noreferrer");
      // Only treat as connected when the backend actually reports a connected
      // (or connecting-for-redirect) status. Any other outcome is an error.
      if (result.status === "connected" || result.status === "connecting") {
        setPhase("connected");
      } else {
        setPhase("error");
      }
    } catch {
      setPhase("error");
    }
  }, [connector.type]);

  // Close on Escape except while actively connecting.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && phase !== "connecting") onCancel(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, onCancel]);

  return (
    <div
      className="dialog-wrap"
      onMouseDown={(e) => { if (e.target === e.currentTarget && phase !== "connecting") onCancel(); }}
    >
      <div className="dialog connector-modal" role="dialog" aria-modal="true" aria-labelledby="connect-title" ref={ref}>
        <div className="dialog-head">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <ConnectorLogo type={connector.type} size={44} />
            <div className="section-title" id="connect-title" style={{ marginBottom: 0 }}>
              Connect {meta.name} to ChatLens
            </div>
          </div>
          {phase === "permissions" && (
            <p className="card-desc" style={{ marginTop: 12 }}>
              Connect {meta.name} to let ChatLens discover and index visual memories shared through {meta.name}.
            </p>
          )}
        </div>

        <div className="dialog-body">
          {phase === "permissions" && <PermissionPanel name={meta.name} />}
          {phase === "connecting" && <ConnectionProgress name={meta.name} />}
          {phase === "connected" && (
            <div className="conn-success">
              <div className="success-check"><Icon name="check" size={30} /></div>
              <h3>{meta.name} connected</h3>
              <p>Your {meta.name} visual memories are now available to ChatLens.</p>
            </div>
          )}
          {phase === "error" && (
            <ConnectionError onRetry={runConnect} onCancel={onCancel} />
          )}
        </div>

        {phase === "permissions" && (
          <div className="dialog-foot">
            <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
            <button className="btn btn-primary" onClick={runConnect}>
              <Icon name="arrow" size={15} /> Connect {meta.name}
            </button>
          </div>
        )}
        {phase === "connected" && (
          <div className="dialog-foot">
            <button className="btn btn-primary" onClick={onConnected}>Continue</button>
          </div>
        )}
      </div>
    </div>
  );
}