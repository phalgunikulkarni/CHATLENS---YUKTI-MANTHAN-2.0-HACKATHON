import { useState, type FormEvent } from "react";
import { useAuth } from "./useAuth";
import { LoginLayout } from "./LoginLayout";
import { AuthField, PasswordField } from "./AuthFields";
import { Icon } from "../../components/Icon";

export function LoginPage({ onGoToSignup }: { onGoToSignup: () => void }) {
  const { login, status, error, clearError } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const busy = status === "authenticating";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await login({ email, password, remember });
    } catch {
      // Error surfaced via context state; form values are preserved.
    }
  };

  return (
    <LoginLayout>
      <h1 className="auth-title">Welcome back</h1>
      <p className="auth-subtitle">Sign in to your visual memory</p>

      {error && (
        <div className="auth-error" role="alert">
          <strong>Unable to sign in</strong>
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={submit} noValidate>
        <AuthField
          id="login-email"
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => { setEmail(e.target.value); if (error) clearError(); }}
          required
        />
        <PasswordField
          id="login-password"
          label="Password"
          autoComplete="current-password"
          placeholder="At least 8 characters"
          value={password}
          onChange={(e) => { setPassword(e.target.value); if (error) clearError(); }}
          required
        />

        <div className="auth-row">
          <label className="auth-check">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
            Remember me
          </label>
          <button type="button" className="auth-link" onClick={() => { /* backend-owned flow */ }}>
            Forgot password?
          </button>
        </div>

        <button type="submit" className="btn btn-primary auth-submit" disabled={busy}>
          {busy ? (<><Icon name="sparkles" size={16} className="spin" /> Signing you in...</>) : "Sign in"}
        </button>
      </form>

      <div className="auth-divider"><span>OR</span></div>

      <button type="button" className="btn btn-ghost auth-social" onClick={() => { /* backend-owned OAuth */ }}>
        <Icon name="database" size={16} /> Continue with Google
      </button>

      <p className="auth-switch">
        Don&apos;t have an account?{" "}
        <button type="button" className="auth-link" onClick={onGoToSignup}>Create account</button>
      </p>
    </LoginLayout>
  );
}