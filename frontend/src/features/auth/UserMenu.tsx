import { useEffect, useRef, useState } from "react";
import { useAuth } from "./useAuth";
import { useDispatch } from "../../hooks";
import { Icon } from "../../components/Icon";
import { LogoutConfirm } from "./LogoutConfirm";
import { ProfileModal } from "../account/ProfileModal";
import { SettingsModal } from "../account/SettingsModal";
import { uid } from "../../utils/format";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p.charAt(0).toUpperCase()).join("") || "U";
}

/** Sidebar user profile + account menu (Profile / Settings / Log out). */
export function UserMenu() {
  const { user, logout } = useAuth();
  const dispatch = useDispatch();
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close the dropdown on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open]);

  if (!user) return null;

  return (
    <div className="user-menu" ref={ref}>
      {open && (
        <div className="user-dropdown" role="menu">
          <button className="user-dropdown-item" role="menuitem" onClick={() => { setOpen(false); setShowProfile(true); }}>
            <Icon name="eye" size={15} /> Profile
          </button>
          <button className="user-dropdown-item" role="menuitem" onClick={() => { setOpen(false); setShowSettings(true); }}>
            <Icon name="sparkles" size={15} /> Settings
          </button>
          <button
            className="user-dropdown-item danger"
            role="menuitem"
            onClick={() => { setOpen(false); setConfirming(true); }}
          >
            <Icon name="arrow" size={15} /> Log out
          </button>
        </div>
      )}

      <button className="user-chip" onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open}>
        <span className="user-avatar">{initials(user.name)}</span>
        <span className="user-meta">
          <span className="user-name">{user.name}</span>
          <span className="user-email">{user.email}</span>
        </span>
        <Icon name="chevron" size={16} style={{ transform: open ? "rotate(-90deg)" : "rotate(90deg)", opacity: 0.7 }} />
      </button>

      {showProfile && <ProfileModal onClose={() => setShowProfile(false)} />}
      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}

      {confirming && (
        <LogoutConfirm
          onCancel={() => setConfirming(false)}
          onConfirm={async () => {
            setConfirming(false);
            dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Logged out", tone: "info" } });
            await logout();
          }}
        />
      )}
    </div>
  );
}