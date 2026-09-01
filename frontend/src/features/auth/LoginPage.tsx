import { useState, type FormEvent } from "react";
import { useAuth } from "./useAuth";
import { AuthLayout } from "./AuthLayout";
import { AuthField, PasswordField } from "./AuthFields";
import { IS_DEV_AUTH } from "../../services/authService";
import { Icon } from "../../components/Icon";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function LoginPage({ onGoToSignup }: { onGoToSignup: () => void }) {
  const { login, status, error, clearError } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const busy = status === "authenticating";

  const validate = (): boolean => {
    const next: { email?: string; password?: string } = {};
    if (!email.trim()) next.email = "Please enter your email address.";
    else if (!EMAIL_RE.test(email.trim())) next.email = "Please enter a valid email address.";
    if (!password) next.password = "Please enter your password.";
    else if (password.length < 8) next.password = "Password must contain at least 8 characters.";
    setFieldErrors(next);
    return Object.keys(next).length === 0;
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (error) clearError();
    // Frontend validation gate - no backend needed to reach a successful demo login.
    if (!validate()) return;
    try {
      await login({ email: email.trim(), password, remember });
    } catch {
      // The dev auth service resolves for valid-looking input, so this path is
      // only reached in unexpected cases; the message is surfaced via context.
    }
  };

  return (
    <AuthLayout>
      <div className="auth-title-row">
        <h1 className="auth-title">Welcome back</h1>
        {IS_DEV_AUTH && <span className="demo-tag" title="Frontend demo sign-in (no backend required)">Demo sign-in</span>}
      </div>
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
          onChange={(e) => { setEmail(e.target.value); if (fieldErrors.email) setFieldErrors((f) => ({ ...f, email: undefined })); if (error) clearError(); }}
          aria-invalid={Boolean(fieldErrors.email)}
        />
        {fieldErrors.email && <p className="field-error" role="alert">{fieldErrors.email}</p>}

        <PasswordField
          id="login-password"
          label="Password"
          autoComplete="current-password"
          placeholder="At least 8 characters"
          value={password}
          onChange={(e) => { setPassword(e.target.value); if (fieldErrors.password) setFieldErrors((f) => ({ ...f, password: undefined })); if (error) clearError(); }}
          aria-invalid={Boolean(fieldErrors.password)}
        />
        {fieldErrors.password && <p className="field-error" role="alert">{fieldErrors.password}</p>}

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
          {busy ? (<><Icon name="sparkles" size={16} className="spin" /> Signing in...</>) : "Sign in"}
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
    </AuthLayout>
  );
}