import type { ViewName } from "../state/types";
import { BrandLogo } from "../components/BrandLogo";
import { Icon, type IconName } from "../components/Icon";
import { IS_BACKEND_CONNECTED, IS_DEMO_MODE } from "../api/client";
import { UserMenu } from "../features/auth/UserMenu";

const NAV: { view: ViewName; label: string; icon: IconName }[] = [
  { view: "search", label: "Search", icon: "search" },
  { view: "library", label: "Memories", icon: "library" },
  { view: "history", label: "Search history", icon: "history" },
  { view: "connectors", label: "Connectors", icon: "layers" },
  { view: "upload", label: "Upload", icon: "upload" },
];

interface Props {
  view: ViewName;
  open: boolean;
  onNavigate: (v: ViewName) => void;
}

export function Sidebar({ view, open, onNavigate }: Props) {
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
      <div className="sidebar-footer">
        <div style={{ marginBottom: 12 }}>
          {IS_DEMO_MODE ? (
            <span className="mock-badge"><Icon name="sparkles" size={12} /> Demo mode</span>
          ) : !IS_BACKEND_CONNECTED ? (
            <span className="mock-badge"><Icon name="database" size={12} /> Backend not connected</span>
          ) : (
            <span className="mock-badge"><Icon name="check" size={12} /> Backend connected</span>
          )}
        </div>
        <UserMenu />
      </div>
    </aside>
  );
}