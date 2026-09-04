import {
  createContext,
  useCallback,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { authService } from "../../services/authService";
import { clearAccountId, setAccountId } from "../../api/accountContext";
import type { AuthState, LoginRequest, RegisterRequest } from "../../services/auth.types";

export interface AuthContextValue extends AuthState {
  isAuthenticated: boolean;
  login: (req: LoginRequest) => Promise<void>;
  register: (req: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

/** Friendly, non-technical messages (never expose raw backend errors). */
function friendlyError(kind: "login" | "register"): string {
  return kind === "login"
    ? "Please check your email and password and try again."
    : "We could not create your account. Please review the form and try again.";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const restored = authService.restore();
  // On session restore, prime the account holder so the very first request
  // after a refresh already carries X-Account-Id (uses the existing
  // stableAccountId-derived user.id; never generates a new id).
  if (restored) {
    setAccountId(restored.user.id);
  } else {
    clearAccountId();
  }
  const [state, setState] = useState<AuthState>(
    restored
      ? { status: "authenticated", user: restored.user, token: restored.token, error: null }
      : { status: "unauthenticated", user: null, token: null, error: null }
  );

  const login = useCallback(async (req: LoginRequest) => {
    setState((s) => ({ ...s, status: "authenticating", error: null }));
    try {
      const res = await authService.login(req);
      // Set the account holder to the signed-in user's stable id. Login always
      // overwrites the holder, so switching account A -> B replaces A's id.
      setAccountId(res.user.id);
      setState({ status: "authenticated", user: res.user, token: res.token, error: null });
    } catch {
      setState({ status: "error", user: null, token: null, error: friendlyError("login") });
      throw new Error("login_failed");
    }
  }, []);

  const register = useCallback(async (req: RegisterRequest) => {
    setState((s) => ({ ...s, status: "authenticating", error: null }));
    try {
      const res = await authService.register(req);
      setAccountId(res.user.id);
      setState({ status: "authenticated", user: res.user, token: res.token, error: null });
    } catch {
      setState({ status: "error", user: null, token: null, error: friendlyError("register") });
      throw new Error("register_failed");
    }
  }, []);

  const logout = useCallback(async () => {
    await authService.logout();
    // Clear the request-layer account id so no header is sent afterward. The
    // in-memory store reset (conversation/results/actions) is driven by the
    // AccountResetBridge effect that observes user.id -> null within the
    // StoreProvider subtree (see AccountResetBridge).
    clearAccountId();
    setState({ status: "unauthenticated", user: null, token: null, error: null });
  }, []);

  const clearError = useCallback(() => {
    setState((s) => (s.status === "error" ? { ...s, status: "unauthenticated", error: null } : s));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      isAuthenticated: state.status === "authenticated" && Boolean(state.user),
      login,
      register,
      logout,
      clearError,
    }),
    [state, login, register, logout, clearError]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}