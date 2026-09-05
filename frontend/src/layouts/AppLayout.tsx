import { useEffect, useState, type ReactNode } from "react";
import { useConversations, useDispatch, useOnlineStatus, useUi } from "../hooks";
import { useChatLens } from "../hooks/useChatLens";
import { useBrowserHistorySync } from "../hooks/useBrowserHistorySync";
import type { ViewName } from "../state/types";
import { Sidebar } from "./Sidebar";
import { Icon } from "../components/Icon";
import { ToastHost } from "../components/ToastHost";

const TITLES: Record<ViewName, string> = {
  search: "Visual memory search",
  library: "Your memory library",
  connectors: "Connect your memories",
  history: "Search history",
};

export function AppLayout({ children }: { children: ReactNode }) {
  const { view, offline } = useUi();
  const conversations = useConversations();
  const c = useChatLens();
  const dispatch = useDispatch();
  const online = useOnlineStatus();
  // Bridge state-driven navigation to the browser history stack (Back/Forward).
  useBrowserHistorySync();
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
      <Sidebar
        view={view}
        open={menuOpen}
        onNavigate={navigate}
        conversations={conversations.summaries}
        activeConversationId={conversations.activeId}
        onNewChat={() => { c.newConversation(); setMenuOpen(false); }}
        onSelectConversation={(id) => { c.selectConversation(id); setMenuOpen(false); }}
      />
      <div className="main">
        {offline && <div className="offline-bar">You are offline. Some actions may not work.</div>}
        <div className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button className="icon-btn hamburger" onClick={() => setMenuOpen((o) => !o)} aria-label="Toggle menu">
              <Icon name="menu" size={18} />
            </button>
            <span className="topbar-title">{TITLES[view]}</span>
          </div>
        </div>

        <main className="content">{children}</main>
      </div>
      <ToastHost />
    </div>
  );
}