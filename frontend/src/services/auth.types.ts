/**
 * Authentication types shared by the auth service, context, and UI.
 * The backend team will own the real auth API; these types make the expected
 * contract explicit so the service layer can be swapped in later.
 */

export interface User {
  id: string;
  name: string;
  email: string;
}

export interface LoginRequest {
  email: string;
  password: string;
  remember?: boolean;
}

export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
}

export interface LoginResponse {
  user: User;
  /** Opaque session token issued by the backend. */
  token: string;
}

export type AuthStatus =
  | "unauthenticated"
  | "authenticating"
  | "authenticated"
  | "error"
  | "session_expired";

export interface AuthState {
  status: AuthStatus;
  user: User | null;
  token: string | null;
  error: string | null;
}