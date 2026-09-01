import { useRef } from "react";
import { useFocusTrap } from "../../hooks";
import { Icon } from "../../components/Icon";

export function LogoutConfirm({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, true, onCancel);
  return (
    <div className="dialog-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onCancel(); }}>
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
          <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" onClick={onConfirm}>Log out</button>
        </div>
      </div>
    </div>
  );
}