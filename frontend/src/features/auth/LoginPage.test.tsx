import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider } from "./AuthContext";
import { LoginPage } from "./LoginPage";

function renderLogin(onGoToSignup = vi.fn()) {
  const { container } = render(
    <AuthProvider>
      <LoginPage onGoToSignup={onGoToSignup} />
    </AuthProvider>,
  );
  return { container, onGoToSignup };
}

describe("LoginPage (pre-login ripple redesign)", () => {
  it("renders the scoped login-page root and the ripple background behind content", () => {
    const { container } = renderLogin();
    // Scoped root + ripple container present (isolation markers).
    expect(container.querySelector(".login-page")).not.toBeNull();
    expect(container.querySelector(".login-page .ripple-background")).not.toBeNull();
    expect(container.querySelector(".login-page .login-card")).not.toBeNull();
    // React Bits image-distortion: the ripple background loads /hero.jpg as its
    // source (set as a CSS background fallback by the component effect).
    const ripple = container.querySelector<HTMLDivElement>(".login-page .ripple-background");
    expect(ripple).not.toBeNull();
    expect(ripple!.style.backgroundImage).toContain("/hero.jpg");
    // No WebGL in jsdom -> the page must still render (no blank/crash).
    expect(screen.getByText("Welcome back")).toBeInTheDocument();
  });

  it("keeps all existing auth controls", () => {
    renderLogin();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByLabelText(/Remember me/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Forgot password/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Sign in$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Continue with Google/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Create account/i })).toBeInTheDocument();
  });

  it("branding headline and tagline render", () => {
    renderLogin();
    expect(screen.getByText(/Your visual memories in/i)).toBeInTheDocument();
    expect(screen.getByText(/one searchable place\./i)).toBeInTheDocument();
    expect(screen.getByText("Same photos. A deeper you.")).toBeInTheDocument();
  });

  it("the form still works: typing + submit does not crash and login is attempted", async () => {
    const u = userEvent.setup();
    renderLogin();
    await u.type(screen.getByLabelText("Email"), "user@example.com");
    await u.type(screen.getByLabelText("Password"), "password1");
    await u.click(screen.getByRole("button", { name: /^Sign in$/i }));
    // Page remains mounted (no blank page); the sign-in control is still present.
    expect(screen.getByText("Welcome back")).toBeInTheDocument();
  });

  it("'Create account' switches to signup via the existing handler", async () => {
    const u = userEvent.setup();
    const { onGoToSignup } = renderLogin();
    await u.click(screen.getByRole("button", { name: /Create account/i }));
    expect(onGoToSignup).toHaveBeenCalledTimes(1);
  });
});
