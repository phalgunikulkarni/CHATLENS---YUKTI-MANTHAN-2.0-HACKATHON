import { useRef } from "react";
import { createPortal } from "react-dom";
import { useFocusTrap } from "../../hooks";
import { Icon } from "../../components/Icon";

/**
 * Logout confirmation dialog.
 *
 * Rendered via a portal into document.body so its fixed-position backdrop is
 * relative to the VIEWPORT, not to the sidebar it is triggered from. The sidebar
 * uses `transform` on narrow viewports, which would otherwise make it the
 * containing block for `position: fixed` descendants — clipping/mis-layering the
 * modal behind page content. The portal escapes that stacking context so the
 * backdrop dims the whole app and the dialog sits clearly in the foreground.
 * Reuses the shared .dialog-wrap/.dialog styling (unchanged visual language).
 */
export function LogoutConfirm({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, true, onCancel);  // handles Escape + focus trap/restore

  const dialog = (
    <div
      className="dialog-wrap"
      data-testid="logout-backdrop"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onCancel(); }}
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
          <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" onClick={onConfirm}>Log out</button>
        </div>
      </div>
    </div>
  );

  // Portal to body when available (browser/jsdom); fall back to inline render.
  return typeof document !== "undefined" ? createPortal(dialog, document.body) : dialog;
}
