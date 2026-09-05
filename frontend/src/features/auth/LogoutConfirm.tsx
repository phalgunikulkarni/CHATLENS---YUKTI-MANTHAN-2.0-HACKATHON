import { useRef } from "react";
import { useFocusTrap } from "../../hooks";
import { Icon } from "../../components/Icon";

/**
 * Logout confirmation dialog. `busy` reflects an in-flight logout: while true the
 * controls are disabled so rapid/duplicate clicks cannot fire multiple logout
 * calls (which previously raced and left auth state inconsistent). onConfirm is
 * invoked at most once per confirmation because the button is disabled the
 * instant logout starts.
 */
export function LogoutConfirm({
  onConfirm,
  onCancel,
  busy = false,
}: {
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  // While logging out, ignore the escape/outside-close so the flow completes.
  useFocusTrap(ref, true, busy ? undefined : onCancel);
  return (
    <div
      className="dialog-wrap"
      onMouseDown={(e) => { if (!busy && e.target === e.currentTarget) onCancel(); }}
    >
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="logout-title" ref={ref} style={{ maxWidth: 420 }}>
        <div className="dialog-head">
          <div className="section-title" id="logout-title" style={{ marginBottom: 0, display: "flex", alignItems: "center", gap: 8 }}>
            <Icon name="arrow" size={18} style={{ color: "var(--accent)" }} /> Log out of ChatLens?
          </div>
          <p className="card-desc" style={{ marginTop: 10 }}>
            You will be returned to the sign-in page. Your memories stay safe.
          </p>
        </div>
        <div className="dialog-foot">
          <button className="btn btn-ghost" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className="btn btn-primary" onClick={onConfirm} disabled={busy} aria-busy={busy}>
            {busy ? (<><Icon name="sparkles" size={15} className="spin" /> Logging out...</>) : "Log out"}
          </button>
        </div>
      </div>
    </div>
  );
}