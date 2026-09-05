import { useCallback, useRef, useState } from "react";
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
  const [loggingOut, setLoggingOut] = useState(false);
  // Hard guard against overlapping logout calls (rapid double-clicks, or a
  // click while a prior logout is still resolving). A ref is synchronous, so it
  // blocks re-entry before React can re-render the disabled button.
  const inFlight = useRef(false);
  const ref = useRef<HTMLDivElement>(null);

  const handleLogout = useCallback(async () => {
    if (inFlight.current) return; // ignore duplicate/rapid confirms
    inFlight.current = true;
    setLoggingOut(true);
    try {
      // Always await; logout() is idempotent (clears storage + account id +
      // auth state). On success `user` becomes null and this menu unmounts.
      await logout();
    } finally {
      // If the component is still mounted (e.g. logout somehow left us
      // authenticated), release the guard and close the dialog so the user is
      // never stuck. On the normal path the component has already unmounted.
      inFlight.current = false;
      setLoggingOut(false);
      setConfirming(false);
    }
  }, [logout]);

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
          busy={loggingOut}
          onCancel={() => { if (!loggingOut) setConfirming(false); }}
          onConfirm={handleLogout}
        />
      )}
    </div>
  );
}