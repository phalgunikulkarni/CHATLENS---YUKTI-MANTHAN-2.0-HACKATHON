import { describe, it, expect, beforeEach } from "vitest";
import { authService } from "./authService";

describe("stable account id", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it("same email -> same id across logins (case/space-insensitive)", async () => {
    const a = await authService.login({ email: "user@example.com", password: "password1" });
    const b = await authService.login({ email: "  USER@Example.com ", password: "password1" });
    expect(a.user.id).toBe(b.user.id);
  });

  it("different emails -> different ids", async () => {
    const a = await authService.login({ email: "a@example.com", password: "password1" });
    const b = await authService.login({ email: "b@example.com", password: "password1" });
    expect(a.user.id).not.toBe(b.user.id);
  });

  it("token is random and not the id", async () => {
    const a = await authService.login({ email: "user@example.com", password: "password1" });
    const b = await authService.login({ email: "user@example.com", password: "password1" });
    expect(a.token).toMatch(/^dev-/);
    expect(a.token).not.toBe(b.token);
    expect(a.user.id).not.toBe(a.token);
  });
});
