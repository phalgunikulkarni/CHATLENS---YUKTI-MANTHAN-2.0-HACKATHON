import type { ViewName } from "../state/types";
import type { ConversationSummary } from "../state/conversations.slice";
import { BrandLogo } from "../components/BrandLogo";
import { Icon, type IconName } from "../components/Icon";
import { UserMenu } from "../features/auth/UserMenu";

const NAV: { view: ViewName; label: string; icon: IconName }[] = [
  { view: "search", label: "Search", icon: "search" },
  { view: "library", label: "Memories", icon: "library" },
  { view: "calendar", label: "Calendar", icon: "calendar" },
  { view: "tasks", label: "Tasks", icon: "tasks" },
  { view: "connectors", label: "Connectors", icon: "layers" },
];

interface Props {
  view: ViewName;
  open: boolean;
  onNavigate: (v: ViewName) => void;
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
}

export function Sidebar({
  view,
  open,
  onNavigate,
  conversations,
  activeConversationId,
  onNewChat,
  onSelectConversation,
}: Props) {
  return (
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <div className="brand">
        <BrandLogo />
        <div>
          <div className="brand-name">ChatLens</div>
          <div className="brand-tag">You remember it. We find it.</div>
        </div>
      </div>
      <nav aria-label="Primary">
        {NAV.map((n) => (
          <button
            key={n.view}
            className={`nav-item ${view === n.view ? "active" : ""}`}
            onClick={() => onNavigate(n.view)}
            aria-current={view === n.view ? "page" : undefined}
          >
            <Icon name={n.icon} size={19} /> {n.label}
          </button>
        ))}
      </nav>

      <div className="conv-section">
        <button className="nav-item new-chat" onClick={onNewChat}>
          <Icon name="sparkles" size={19} /> New Chat
        </button>
        <div className="conv-label">Conversations</div>
        {conversations.length === 0 ? (
          <div className="conv-empty">No conversations yet</div>
        ) : (
          <div className="conv-list">
            {conversations.map((c) => {
              const active = c.id === activeConversationId;
              return (
                <button
                  key={c.id}
                  className={`nav-item conv-item ${active ? "active" : ""}`}
                  onClick={() => onSelectConversation(c.id)}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon name="history" size={17} />
                  <span className="conv-title">{c.title || "New chat"}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="sidebar-footer">
        <UserMenu />
      </div>
    </aside>
  );
}
