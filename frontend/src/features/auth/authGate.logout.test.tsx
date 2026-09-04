import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { AuthProvider } from "./AuthContext";
import { AuthGate } from "./AuthGate";
import { useAuth } from "./useAuth";

/**
 * UI-level logout regression coverage for AuthGate.
 *
 * AuthGate owns two pieces of transient UI state that a logout must not leave
 * stale:
 *   - `mode` ("login" | "signup"): which auth page to show while unauthenticated.
 *   - `showSuccess` / `successMode`: the brief welcome popup shown ONLY on the
 *      unauthenticated -> authenticated transition.
 *
 * A logout must return the user to the SIGN-IN page and must not leave a queued
 * welcome popup. A top-level control (always mounted, inside AuthProvider but
 * outside AuthGate) drives logout across auth states.
 */
function LogoutControl() {
  const { logout } = useAuth();
  return <button onClick={() => logout()}>top-logout</button>;
}

function renderGate() {
  return render(
    <AuthProvider>
      <LogoutControl />
      <AuthGate>
        <div data-testid="protected">Protected App</div>
      </AuthGate>
    </AuthProvider>,
  );
}

async function clickText(label: string) {
  await act(async () => {
    screen.getByText(label).click();
  });
}

async function fill(placeholder: RegExp, value: string) {
  const el = screen.getByPlaceholderText(placeholder) as HTMLInputElement;
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")!.set!;
    setter.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function clickButton(name: RegExp) {
  await act(async () => {
    screen.getByRole("button", { name }).click();
  });
}

async function goToSignupAndRegister() {
  // The LoginPage "Create account" link switches to the signup page.
  await clickText("Create account");
  await fill(/your name/i, "Gate User");
  await fill(/you@example\.com/i, "gate.user@example.com");
  await fill(/at least 8 characters/i, "password1");
  await fill(/re-enter your password/i, "password1");
  // The signup submit button is also labelled "Create account".
  await clickButton(/create account/i);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(800); // dev auth latency
  });
}

describe("AuthGate logout (UI transition)", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it("after signing up then logging out, AuthGate shows the SIGN-IN page (not the signup page)", async () => {
    renderGate();

    await goToSignupAndRegister();
    expect(screen.getByTestId("protected")).not.toBeNull();

    // Log out BEFORE the success popup's 1.6s timer completes.
    await clickText("top-logout");

    // Should return to the SIGN-IN page. Before the fix, `mode` stayed "signup"
    // so the Signup page ("Create your ChatLens account") was shown instead.
    expect(screen.getByText("Welcome back")).not.toBeNull();
    expect(screen.queryByText("Create your ChatLens account")).toBeNull();
  });

  it("logout does not leave a stale success popup queued", async () => {
    renderGate();

    // Sign up (queues a success popup) then log out before it auto-dismisses.
    await goToSignupAndRegister();
    expect(screen.queryByRole("alertdialog", { name: /success/i })).not.toBeNull();

    await clickText("top-logout");

    // No success popup should remain visible on the sign-in screen.
    expect(screen.queryByRole("alertdialog", { name: /success/i })).toBeNull();
  });
});
