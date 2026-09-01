import { useRef } from "react";
import { useDispatch, useSettings, useUi, useFocusTrap } from "../../hooks";
import { applyTheme, type DefaultView, type ThemePref } from "../../state/settings.slice";
import { useChatLens } from "../../hooks/useChatLens";
import { Icon } from "../../components/Icon";
import { uid } from "../../utils/format";

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className={`toggle ${checked ? "on" : ""}`}
      onClick={() => onChange(!checked)}
    >
      <span className="toggle-knob" />
    </button>
  );
}

/** Settings modal. Changes take effect immediately and persist to localStorage. */
export function SettingsModal({ onClose }: { onClose: () => void }) {
  const settings = useSettings();
  const dispatch = useDispatch();
  const c = useChatLens();
  const { searchHistory } = useUi();
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, true, onClose);

  const change = (patch: Partial<typeof settings>) => dispatch({ type: "SETTINGS_CHANGED", patch });

  const setTheme = (theme: ThemePref) => {
    change({ theme });
    applyTheme(theme);
  };

  return (
    <div className="dialog-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="dialog settings-modal" role="dialog" aria-modal="true" aria-labelledby="settings-title" ref={ref}>
        <div className="dialog-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div className="section-title" id="settings-title" style={{ marginBottom: 0 }}>Settings</div>
          <button className="icon-btn" onClick={onClose} aria-label="Close settings"><Icon name="close" size={18} /></button>
        </div>

        <div className="dialog-body settings-body">
          <section className="settings-section">
            <h4>Appearance</h4>
            <div className="seg">
              {(["light", "dark", "system"] as ThemePref[]).map((t) => (
                <button key={t} className={`seg-btn ${settings.theme === t ? "active" : ""}`} onClick={() => setTheme(t)}>
                  {t === "light" ? "Light" : t === "dark" ? "Dark" : "System"}
                </button>
              ))}
            </div>
          </section>

          <section className="settings-section">
            <h4>Search</h4>
            <div className="settings-row">
              <span>Results per page</span>
              <div className="seg">
                {[12, 24, 48].map((n) => (
                  <button key={n} className={`seg-btn ${settings.resultsPerPage === n ? "active" : ""}`} onClick={() => change({ resultsPerPage: n })}>
                    {n}
                  </button>
                ))}
              </div>
            </div>
            <div className="settings-row">
              <span>Default view</span>
              <div className="seg">
                {(["grid", "list"] as DefaultView[]).map((v) => (
                  <button key={v} className={`seg-btn ${settings.defaultView === v ? "active" : ""}`} onClick={() => change({ defaultView: v })}>
                    {v === "grid" ? "Grid" : "List"}
                  </button>
                ))}
              </div>
            </div>
          </section>

          <section className="settings-section">
            <h4>Privacy</h4>
            <div className="settings-row">
              <span>Prefer local image processing</span>
              <Toggle checked={settings.localProcessing} onChange={(v) => change({ localProcessing: v })} label="Prefer local image processing" />
            </div>
            <div className="settings-row">
              <span>Search history {searchHistory.length > 0 ? `(${searchHistory.length})` : ""}</span>
              <button className="btn btn-subtle" disabled={searchHistory.length === 0} onClick={c.clearHistory}>
                Clear history
              </button>
            </div>
          </section>

          <section className="settings-section">
            <h4>Notifications</h4>
            <div className="settings-row">
              <span>Processing completed</span>
              <Toggle checked={settings.notifyProcessing} onChange={(v) => change({ notifyProcessing: v })} label="Processing completed notifications" />
            </div>
            <div className="settings-row">
              <span>Search updates</span>
              <Toggle checked={settings.notifySearch} onChange={(v) => change({ notifySearch: v })} label="Search update notifications" />
            </div>
          </section>
        </div>

        <div className="dialog-foot">
          <button className="btn btn-primary" onClick={() => { dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Settings saved", tone: "success" } }); onClose(); }}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}