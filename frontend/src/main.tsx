import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { applyTheme, initialSettingsState } from "./state/settings.slice";
import "./styles/global.css";

// Apply the persisted theme before first paint.
applyTheme(initialSettingsState.theme);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);