import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider } from "./AuthContext";
import { useAuth } from "./useAuth";
import { UserMenu } from "./UserMenu";
import { authService } from "../../services/authService";

const CREDS = { email: "menu.user@example.com", password: "password1", remember: true };

/**
 * Deterministic, single-shot logout from the sidebar menu.
 *
 * Reproduces the inconsistency guard: rapid/duplicate confirm clicks must fire
 * exactly ONE logout, the confirm button must be disabled while logging out,
 * and the session must end (UserMenu unmounts when user becomes null).
 */
function Harness() {
  const { isAuthenticated, login } = useAuth();
  return (
    <div>
      {!isAuthenticated && <button onClick={() => login(CREDS)}>login</button>}
      <div data-testid="auth">{isAuthenticated ? "authed" : "anon"}</div>
      <UserMenu />
    </div>
  );
}

describe("UserMenu logout (deterministic, single-shot)", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  afterEach(() => vi.restoreAllMocks());

  it("fires exactly one logout on rapid confirm clicks and ends the session", async () => {
    const logoutSpy = vi.spyOn(authService, "logout");
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    );

    // Sign in so the UserMenu (and its profile chip) renders.
    await user.click(screen.getByText("login"));
    await screen.findByText("authed");

    // Open the account menu, then choose Log out to open the confirm dialog.
    await user.click(screen.getByRole("button", { name: /menu\.user@example\.com|menu user/i }).closest("button")!);
    await user.click(screen.getByRole("menuitem", { name: /log out/i }));

    const confirm = await screen.findByRole("button", { name: /^log out$/i });

    // Rapidly click confirm several times; only one logout must be issued.
    await act(async () => {
      confirm.click();
      confirm.click();
      confirm.click();
    });

    await waitFor(() => expect(screen.getByTestId("auth").textContent).toBe("anon"));
    expect(logoutSpy).toHaveBeenCalledTimes(1);
  });

  it("disables the confirm button while logout is in flight", async () => {
    // Make logout slow so we can observe the disabled/busy state.
    let release: () => void = () => {};
    vi.spyOn(authService, "logout").mockImplementation(
      () => new Promise<void>((resolve) => { release = resolve; }),
    );
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    );
    await user.click(screen.getByText("login"));
    await screen.findByText("authed");
    await user.click(screen.getByRole("button", { name: /menu\.user@example\.com|menu user/i }).closest("button")!);
    await user.click(screen.getByRole("menuitem", { name: /log out/i }));

    const confirm = await screen.findByRole("button", { name: /^log out$/i });
    await act(async () => { confirm.click(); });

    // While in flight the confirm control is disabled (prevents duplicates).
    await waitFor(() => {
      const busy = screen.getByRole("button", { name: /logging out/i });
      expect(busy).toBeDisabled();
    });

    // Complete the logout; session ends.
    await act(async () => { release(); });
    await waitFor(() => expect(screen.getByTestId("auth").textContent).toBe("anon"));
  });
});