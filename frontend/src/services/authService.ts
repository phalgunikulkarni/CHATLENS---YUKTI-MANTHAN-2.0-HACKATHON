import type { LoginRequest, LoginResponse, RegisterRequest, User } from "./auth.types";

/**
 * ============================================================================
 * DEVELOPMENT-ONLY authentication service.
 * ============================================================================
 *
 * The ChatLens backend does not currently expose authentication endpoints, so
 * this module provides a LOCAL, DEV-ONLY implementation so the login/signup UX
 * can be built and demoed. It is NOT secure and is NOT a real auth system:
 *
 *   - No passwords are stored. Credentials are validated for shape only; the
 *     "password" is never persisted anywhere.
 *   - The "token" is a random opaque string with no cryptographic meaning.
 *   - Accounts registered in a session live only in memory + a local marker.
 *
 * When the backend team provides real endpoints (e.g. POST /auth/login,
 * POST /auth/register, POST /auth/logout), replace the body of `login`,
 * `register`, and `logout` with `fetch` calls behind VITE_API_BASE_URL. The
 * AuthContext consumes only this interface, so no UI changes are required.
 */

export interface AuthService {
  login(req: LoginRequest): Promise<LoginResponse>;
  register(req: RegisterRequest): Promise<LoginResponse>;
  logout(): Promise<void>;
  /** Restore a session from persisted storage on app start, if any. */
  restore(): { user: User; token: string } | null;
}

const SESSION_KEY = "chatlens.auth.session.v1";
const DEV_LATENCY = 700;

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function makeToken(): string {
  // Opaque, non-cryptographic dev token. Not a credential.
  return `dev-${Math.random().toString(36).slice(2)}-${Date.now().toString(36)}`;
}

function nameFromEmail(email: string): string {
  const local = email.split("@")[0] ?? "You";
  return local
    .split(/[._-]/)
    .filter(Boolean)
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" ") || "You";
}

function persist(session: { user: User; token: string }, remember: boolean): void {
  try {
    const store = remember ? localStorage : sessionStorage;
    store.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    // Storage may be unavailable; the session simply won't survive a reload.
  }
}

class DevAuthService implements AuthService {
  async login(req: LoginRequest): Promise<LoginResponse> {
    await delay(DEV_LATENCY);
    // Shape validation only. Never checks a stored password (there is none).
    if (!req.email.includes("@") || req.password.length < 8) {
      throw new Error("INVALID_CREDENTIALS");
    }
    const user: User = { id: makeToken(), name: nameFromEmail(req.email), email: req.email };
    const session = { user, token: makeToken() };
    persist(session, Boolean(req.remember));
    return session;
  }

  async register(req: RegisterRequest): Promise<LoginResponse> {
    await delay(DEV_LATENCY);
    if (!req.email.includes("@") || req.password.length < 8) {
      throw new Error("INVALID_REGISTRATION");
    }
    const user: User = { id: makeToken(), name: req.name.trim() || nameFromEmail(req.email), email: req.email };
    const session = { user, token: makeToken() };
    persist(session, true);
    return session;
  }

  async logout(): Promise<void> {
    try {
      localStorage.removeItem(SESSION_KEY);
      sessionStorage.removeItem(SESSION_KEY);
    } catch {
      // ignore
    }
  }

  restore(): { user: User; token: string } | null {
    try {
      const raw = localStorage.getItem(SESSION_KEY) ?? sessionStorage.getItem(SESSION_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as { user: User; token: string };
      if (parsed?.user?.email && parsed?.token) return parsed;
      return null;
    } catch {
      return null;
    }
  }
}

/**
 * The active auth service. Swap `DevAuthService` for an HTTP-backed service once
 * the backend provides endpoints. Everything else consumes this instance.
 */
export const authService: AuthService = new DevAuthService();

/** True while running against the dev-only auth implementation. */
export const IS_DEV_AUTH = true;