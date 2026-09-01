import { useEffect, useState, type ReactNode } from "react";
import { useDispatch, useOnlineStatus, useUi } from "../hooks";
import type { ViewName } from "../state/types";
import { Sidebar } from "./Sidebar";
import { Icon } from "../components/Icon";
import { ToastHost } from "../components/ToastHost";

const TITLES: Record<ViewName, string> = {
  search: "Visual memory search",
  library: "Your memory library",
  history: "Search history",
  upload: "Add memories",
  connectors: "Connect your memories",
};

export function AppLayout({ children }: { children: ReactNode }) {
  const { view, offline, showImageReminder } = useUi();
  const dispatch = useDispatch();
  const online = useOnlineStatus();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    dispatch({ type: "OFFLINE_CHANGED", offline: !online });
  }, [online, dispatch]);

  const navigate = (v: ViewName) => {
    dispatch({ type: "VIEW_CHANGED", view: v });
    setMenuOpen(false);
  };

  return (
    <div className="app-shell">
      {menuOpen && <div className="scrim" onClick={() => setMenuOpen(false)} />}
      <Sidebar view={view} open={menuOpen} onNavigate={navigate} />
      <div className="main">
        {offline && <div className="offline-bar">You are offline. Some actions may not work.</div>}
        <div className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button className="icon-btn hamburger" onClick={() => setMenuOpen((o) => !o)} aria-label="Toggle menu">
              <Icon name="menu" size={18} />
            </button>
            <span className="topbar-title">{TITLES[view]}</span>
          </div>
          <button className="btn btn-subtle" onClick={() => navigate("upload")}>
            <Icon name="upload" size={16} /> Upload
          </button>
        </div>

        {showImageReminder && (
          <div className="reminder-bar" role="note">
            <span className="reminder-text">
              <Icon name="image" size={16} /> Add your visual memories to start searching.
            </span>
            <span className="reminder-actions">
              <button className="btn btn-primary" onClick={() => { navigate("upload"); dispatch({ type: "IMAGE_REMINDER_SET", show: false }); }}>
                <Icon name="upload" size={15} /> Upload images
              </button>
              <button className="icon-btn" aria-label="Dismiss reminder" onClick={() => dispatch({ type: "IMAGE_REMINDER_SET", show: false })}>
                <Icon name="close" size={16} />
              </button>
            </span>
          </div>
        )}

        <main className="content">{children}</main>
      </div>
      <ToastHost />
    </div>
  );
}