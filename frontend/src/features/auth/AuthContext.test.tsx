import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider } from "./AuthContext";
import { AccountResetBridge } from "./AccountResetBridge";
import { useAuth } from "./useAuth";
import { StoreProvider } from "../../state/store";
import { useDispatch, useResults } from "../../hooks/useStore";
import { getAccountId } from "../../api/accountContext";

/**
 * Feature: account-scoped-chat-and-isolation (Phase A), Tasks 1.3 + 1.5.
 * Verifies the account holder is set on login and cleared on logout, and that
 * the AccountResetBridge resets in-memory results when the account changes
 * (login -> logout, and A -> B). Validates: Requirements R1.2, R1.3, R1.4.
 */

const CREDS_A = { email: "a.user@example.com", password: "password1", remember: true };
const CREDS_B = { email: "b.user@example.com", password: "password1", remember: true };

function Harness() {
  const { user, login, logout } = useAuth();
  const dispatch = useDispatch();
  const results = useResults();
  return (
    <div>
      <button onClick={() => login(CREDS_A)}>login-a</button>
      <button onClick={() => login(CREDS_B)}>login-b</button>
      <button onClick={() => logout()}>logout</button>
      <button onClick={() => dispatch({ type: "RESULTS_REPLACED", items: [{ id: "r1" } as never], query: "cats" })}>
        seed
      </button>
      <div data-testid="uid">{user?.id ?? ""}</div>
      <div data-testid="holder">{getAccountId() ?? ""}</div>
      <div data-testid="result-count">{results.items.length}</div>
    </div>
  );
}

function renderApp() {
  return render(
    <AuthProvider>
      <StoreProvider>
        <AccountResetBridge>
          <Harness />
        </AccountResetBridge>
      </StoreProvider>
    </AuthProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

describe("AuthContext account holder + reset bridge", () => {
  it("login sets the holder to user.id (the stableAccountId)", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByText("login-a"));
    // Dev auth is async (simulated latency); wait for the authenticated state.
    await waitFor(() => expect(screen.getByTestId("uid").textContent).toMatch(/^acct-/), { timeout: 3000 });
    const uid = screen.getByTestId("uid").textContent;
    expect(screen.getByTestId("holder").textContent).toBe(uid);
  });

  it("logout clears the holder and resets in-memory results", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByText("login-a"));
    await waitFor(() => expect(screen.getByTestId("holder").textContent).toMatch(/^acct-/), { timeout: 3000 });

    // Seed some in-memory results, then log out.
    await user.click(screen.getByText("seed"));
    expect(screen.getByTestId("result-count").textContent).toBe("1");

    await user.click(screen.getByText("logout"));

    // Holder cleared and results reset by the bridge (account id -> null).
    await waitFor(() => expect(screen.getByTestId("result-count").textContent).toBe("0"), { timeout: 3000 });
    expect(screen.getByTestId("holder").textContent).toBe("");
  });

  it("switching account A -> B overwrites the holder and resets prior results", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByText("login-a"));
    await waitFor(() => expect(screen.getByTestId("holder").textContent).toMatch(/^acct-/), { timeout: 3000 });
    const idA = screen.getByTestId("holder").textContent;

    await user.click(screen.getByText("seed"));
    expect(screen.getByTestId("result-count").textContent).toBe("1");

    // Login as B (different account) overwrites the holder.
    await user.click(screen.getByText("login-b"));
    await waitFor(() => expect(screen.getByTestId("holder").textContent).not.toBe(idA), { timeout: 3000 });
    const idB = screen.getByTestId("holder").textContent;
    expect(idB).toMatch(/^acct-/);
    expect(idB).not.toBe(idA);
    // Bridge saw the id change and cleared A's results.
    await waitFor(() => expect(screen.getByTestId("result-count").textContent).toBe("0"), { timeout: 3000 });
  });
});
