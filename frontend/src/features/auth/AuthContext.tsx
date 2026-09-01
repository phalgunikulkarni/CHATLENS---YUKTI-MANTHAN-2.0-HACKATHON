import {
  createContext,
  useCallback,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { authService } from "../../services/authService";
import type { AuthState, LoginRequest, RegisterRequest } from "../../services/auth.types";

export interface AuthContextValue extends AuthState {
  isAuthenticated: boolean;
  login: (req: LoginRequest) => Promise<void>;
  register: (req: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (name: string) => Promise<void>;
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
  const [state, setState] = useState<AuthState>(
    restored
      ? { status: "authenticated", user: restored.user, token: restored.token, error: null }
      : { status: "unauthenticated", user: null, token: null, error: null }
  );

  const login = useCallback(async (req: LoginRequest) => {
    setState((s) => ({ ...s, status: "authenticating", error: null }));
    try {
      const res = await authService.login(req);
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
      setState({ status: "authenticated", user: res.user, token: res.token, error: null });
    } catch {
      setState({ status: "error", user: null, token: null, error: friendlyError("register") });
      throw new Error("register_failed");
    }
  }, []);

  const logout = useCallback(async () => {
    await authService.logout();
    setState({ status: "unauthenticated", user: null, token: null, error: null });
  }, []);

  const updateProfile = useCallback(async (name: string) => {
    const user = await authService.updateProfile(name);
    setState((s) => ({ ...s, user }));
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
      updateProfile,
      clearError,
    }),
    [state, login, register, logout, updateProfile, clearError]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}