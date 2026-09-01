import { useRef, useState } from "react";
import { useAuth } from "./useAuth";
import { Icon } from "../../components/Icon";
import { LogoutConfirm } from "./LogoutConfirm";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p.charAt(0).toUpperCase()).join("") || "U";
}

/** Sidebar user profile + menu (Profile / Settings / Log out). */
export function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  if (!user) return null;

  return (
    <div className="user-menu" ref={ref}>
      {open && (
        <div className="user-dropdown" role="menu">
          <button className="user-dropdown-item" role="menuitem" onClick={() => setOpen(false)}>
            <Icon name="eye" size={15} /> Profile
          </button>
          <button className="user-dropdown-item" role="menuitem" onClick={() => setOpen(false)}>
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

      {confirming && (
        <LogoutConfirm
          onCancel={() => setConfirming(false)}
          onConfirm={async () => { setConfirming(false); await logout(); }}
        />
      )}
    </div>
  );
}