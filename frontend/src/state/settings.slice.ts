/**
 * User settings that actually change frontend behavior. Persisted to
 * localStorage for the MVP; ready to be replaced by a backend profile later.
 * No sensitive data is stored.
 */

export type ThemePref = "light" | "dark" | "system";
export type DefaultView = "grid" | "list";

export interface SettingsState {
  theme: ThemePref;
  resultsPerPage: number;
  defaultView: DefaultView;
  localProcessing: boolean;
  notifyProcessing: boolean;
  notifySearch: boolean;
}

const KEY = "chatlens.settings.v1";

export const defaultSettings: SettingsState = {
  theme: "system",
  resultsPerPage: 12,
  defaultView: "grid",
  localProcessing: true,
  notifyProcessing: true,
  notifySearch: true,
};

function load(): SettingsState {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return defaultSettings;
    return { ...defaultSettings, ...(JSON.parse(raw) as Partial<SettingsState>) };
  } catch {
    return defaultSettings;
  }
}

function persist(s: SettingsState): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    // ignore
  }
}

export const initialSettingsState: SettingsState = load();

export type SettingsAction =
  | { type: "SETTINGS_CHANGED"; patch: Partial<SettingsState> }
  | { type: "SETTINGS_RESET" };

export function settingsReducer(state: SettingsState, action: SettingsAction): SettingsState {
  switch (action.type) {
    case "SETTINGS_CHANGED": {
      const next = { ...state, ...action.patch };
      persist(next);
      return next;
    }
    case "SETTINGS_RESET":
      persist(defaultSettings);
      return { ...defaultSettings };
    default:
      return state;
  }
}

/** Apply the theme to the document root. Called on load and on change. */
export function applyTheme(theme: ThemePref): void {
  const resolved =
    theme === "system"
      ? (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light")
      : theme;
  document.documentElement.dataset.theme = resolved;
}