import { describe, it, expect, beforeEach } from "vitest";
import { authService } from "./authService";

describe("Dev auth service (development-only, not secure)", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it("rejects malformed credentials without a stored account", async () => {
    await expect(authService.login({ email: "bad", password: "short" })).rejects.toThrow();
  });

  it("issues a session for well-formed credentials", async () => {
    const res = await authService.login({ email: "user@example.com", password: "password1", remember: true });
    expect(res.user.email).toBe("user@example.com");
    expect(res.token).toMatch(/^dev-/);
  });

  it("never persists the password anywhere", async () => {
    await authService.login({ email: "user@example.com", password: "supersecret9", remember: true });
    const dump = JSON.stringify({ ls: { ...localStorage }, ss: { ...sessionStorage } });
    expect(dump).not.toContain("supersecret9");
  });

  it("remember=false does not persist to localStorage", async () => {
    await authService.login({ email: "user@example.com", password: "password1", remember: false });
    expect(localStorage.getItem("chatlens.auth.session.v1")).toBeNull();
    expect(sessionStorage.getItem("chatlens.auth.session.v1")).not.toBeNull();
  });

  it("restore returns a persisted session and null after logout", async () => {
    await authService.register({ name: "Test User", email: "t@example.com", password: "password1" });
    expect(authService.restore()?.user.email).toBe("t@example.com");
    await authService.logout();
    expect(authService.restore()).toBeNull();
  });
});