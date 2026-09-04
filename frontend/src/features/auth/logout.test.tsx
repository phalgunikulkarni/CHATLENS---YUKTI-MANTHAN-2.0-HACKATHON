import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider } from "./AuthContext";
import { useAuth } from "./useAuth";
import { authService } from "../../services/authService";

const SESSION_KEY = "chatlens.auth.session.v1";
const ONBOARDING_PREFIX = "chatlens.onboarding.imageAccess.v1";
const CREDS = { email: "logout.user@example.com", password: "password1", remember: true };

/**
 * Tiny harness that consumes the real AuthContext. Buttons drive login/logout;
 * text nodes expose the observable state the logout bug would affect.
 */
function Harness() {
  const { isAuthenticated, user, login, logout } = useAuth();
  const sessionExists =
    localStorage.getItem(SESSION_KEY) !== null || sessionStorage.getItem(SESSION_KEY) !== null;
  return (
    <div>
      <button onClick={() => login(CREDS)}>login</button>
      <button onClick={() => logout()}>logout</button>
      <div data-testid="auth">{isAuthenticated ? "authed" : "anon"}</div>
      <div data-testid="uid">{user?.id ?? ""}</div>
      <div data-testid="session">{sessionExists ? "session" : "no-session"}</div>
    </div>
  );
}

describe("Logout flow (frontend auth)", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it("A. login authenticates and persists the session key to localStorage", async () => {
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    );
    await user.click(screen.getByText("login"));
    await screen.findByText("authed");
    expect(screen.getByTestId("auth").textContent).toBe("authed");
    expect(localStorage.getItem(SESSION_KEY)).not.toBeNull();
  });

  it("B. logout flips isAuthenticated to false", async () => {
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    );
    await user.click(screen.getByText("login"));
    await screen.findByText("authed");
    await user.click(screen.getByText("logout"));
    await screen.findByText("anon");
    expect(screen.getByTestId("auth").textContent).toBe("anon");
  });

  it("C. logout clears BOTH localStorage and sessionStorage session keys", async () => {
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    );
    await user.click(screen.getByText("login"));
    await screen.findByText("authed");
    await user.click(screen.getByText("logout"));
    await screen.findByText("anon");
    expect(localStorage.getItem(SESSION_KEY)).toBeNull();
    expect(sessionStorage.getItem(SESSION_KEY)).toBeNull();
  });

  it("D. after logout, restore() returns null and a fresh provider mounts unauthenticated (refresh)", async () => {
    const user = userEvent.setup();
    const { unmount } = render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    );
    await user.click(screen.getByText("login"));
    await screen.findByText("authed");
    await user.click(screen.getByText("logout"));
    await screen.findByText("anon");

    // restore() is the source of truth used on app start / refresh.
    expect(authService.restore()).toBeNull();

    // Simulate a browser refresh: unmount and remount a fresh provider.
    unmount();
    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    );
    expect(screen.getByTestId("auth").textContent).toBe("anon");
  });

  it("E. login again with the same account re-authenticates", async () => {
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    );
    await user.click(screen.getByText("login"));
    await screen.findByText("authed");
    await user.click(screen.getByText("logout"));
    await screen.findByText("anon");
    await user.click(screen.getByText("login"));
    await screen.findByText("authed");
    expect(screen.getByTestId("auth").textContent).toBe("authed");
  });

  it("F. logout preserves the onboarding (device access) marker but does not authenticate", async () => {
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    );
    // Login once to learn the account's stable id.
    await user.click(screen.getByText("login"));
    await screen.findByText("authed");
    const uid = screen.getByTestId("uid").textContent as string;
    expect(uid).toBeTruthy();

    // Pre-seed the device-level onboarding marker for the stable id.
    const marker = `${ONBOARDING_PREFIX}:${uid}`;
    localStorage.setItem(marker, "granted");

    await user.click(screen.getByText("logout"));
    await screen.findByText("anon");

    // (a) device-level access marker survives logout.
    expect(localStorage.getItem(marker)).toBe("granted");
    // (b) but the surviving marker does NOT authenticate.
    expect(screen.getByTestId("auth").textContent).toBe("anon");
    expect(authService.restore()).toBeNull();
  });
});
