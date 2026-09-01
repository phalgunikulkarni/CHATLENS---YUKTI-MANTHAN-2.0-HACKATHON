import { useRef, useState } from "react";
import { useAuth } from "../auth/useAuth";
import { useConnectors, useDispatch, useIngestion, useUi, useFocusTrap } from "../../hooks";
import { Icon } from "../../components/Icon";
import { uid } from "../../utils/format";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p.charAt(0).toUpperCase()).join("") || "U";
}

/**
 * Profile modal. Stats are derived from ACTUAL frontend state (uploaded images,
 * saved searches, connected sources) - never randomly generated. Name editing is
 * a safe frontend-only demo edit; no sensitive data is stored.
 */
export function ProfileModal({ onClose }: { onClose: () => void }) {
  const { user, updateProfile } = useAuth();
  const { queue } = useIngestion();
  const { searchHistory } = useUi();
  const { items: connectors } = useConnectors();
  const dispatch = useDispatch();
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, true, onClose);

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(user?.name ?? "");

  if (!user) return null;

  const memories = queue.filter((q) => q.validation.valid).length;
  const savedSearches = searchHistory.length;
  const connectedSources = connectors.filter((c) => c.status === "connected").length;

  const save = async () => {
    await updateProfile(name);
    setEditing(false);
    dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Profile updated", tone: "success" } });
  };

  return (
    <div className="dialog-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="dialog profile-modal" role="dialog" aria-modal="true" aria-labelledby="profile-title" ref={ref}>
        <div className="dialog-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div className="section-title" id="profile-title" style={{ marginBottom: 0 }}>Profile</div>
          <button className="icon-btn" onClick={onClose} aria-label="Close profile"><Icon name="close" size={18} /></button>
        </div>

        <div className="dialog-body">
          <div className="profile-head">
            <span className="profile-avatar">{initials(user.name)}</span>
            <div style={{ minWidth: 0 }}>
              {editing ? (
                <input
                  className="auth-input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  aria-label="Display name"
                  style={{ maxWidth: 240 }}
                />
              ) : (
                <div className="profile-name">{user.name}</div>
              )}
              <div className="profile-email">{user.email}</div>
              <span className="demo-tag" style={{ marginTop: 6 }}>Demo account</span>
            </div>
          </div>

          <div className="profile-stats">
            <div className="stat"><span className="stat-num">{memories}</span><span className="stat-label">Visual memories</span></div>
            <div className="stat"><span className="stat-num">{savedSearches}</span><span className="stat-label">Saved searches</span></div>
            <div className="stat"><span className="stat-num">{connectedSources}</span><span className="stat-label">Connected sources</span></div>
          </div>
        </div>

        <div className="dialog-foot">
          {editing ? (
            <>
              <button className="btn btn-ghost" onClick={() => { setEditing(false); setName(user.name); }}>Cancel</button>
              <button className="btn btn-primary" onClick={save}>Save</button>
            </>
          ) : (
            <button className="btn btn-ghost" onClick={() => setEditing(true)}>
              <Icon name="sparkles" size={15} /> Edit profile
            </button>
          )}
        </div>
      </div>
    </div>
  );
}