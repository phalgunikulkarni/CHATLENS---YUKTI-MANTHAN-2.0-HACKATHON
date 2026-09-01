import { useMemo, useState, type FormEvent } from "react";
import { useAuth } from "./useAuth";
import { AuthLayout } from "./AuthLayout";
import { AuthField, PasswordField } from "./AuthFields";
import { Icon } from "../../components/Icon";

interface Rule {
  label: string;
  ok: boolean;
}

export function SignupPage({ onGoToLogin }: { onGoToLogin: () => void }) {
  const { register, status, error, clearError } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const busy = status === "authenticating";

  const rules = useMemo<Rule[]>(
    () => [
      { label: "At least 8 characters", ok: password.length >= 8 },
      { label: "Contains a number", ok: /\d/.test(password) },
      { label: "Passwords match", ok: password.length > 0 && password === confirm },
    ],
    [password, confirm]
  );
  const allValid = rules.every((r) => r.ok) && email.includes("@") && name.trim().length > 0;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!allValid) return;
    try {
      await register({ name, email, password });
    } catch {
      // Error surfaced via context state.
    }
  };

  return (
    <AuthLayout>
      <h1 className="auth-title">Create your ChatLens account</h1>
      <p className="auth-subtitle">Start searching your visual memories</p>

      {error && (
        <div className="auth-error" role="alert">
          <strong>Unable to create account</strong>
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={submit} noValidate>
        <AuthField
          id="signup-name"
          label="Full name"
          autoComplete="name"
          placeholder="Your name"
          value={name}
          onChange={(e) => { setName(e.target.value); if (error) clearError(); }}
          required
        />
        <AuthField
          id="signup-email"
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => { setEmail(e.target.value); if (error) clearError(); }}
          required
        />
        <PasswordField
          id="signup-password"
          label="Password"
          autoComplete="new-password"
          placeholder="At least 8 characters"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <PasswordField
          id="signup-confirm"
          label="Confirm password"
          autoComplete="new-password"
          placeholder="Re-enter your password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
        />

        <ul className="auth-rules" aria-label="Password requirements">
          {rules.map((r) => (
            <li key={r.label} className={r.ok ? "ok" : ""}>
              <Icon name={r.ok ? "check" : "close"} size={14} /> {r.label}
            </li>
          ))}
        </ul>

        <button type="submit" className="btn btn-primary auth-submit" disabled={busy || !allValid}>
          {busy ? (<><Icon name="sparkles" size={16} className="spin" /> Creating your account...</>) : "Create account"}
        </button>
      </form>

      <p className="auth-switch">
        Already have an account?{" "}
        <button type="button" className="auth-link" onClick={onGoToLogin}>Sign in</button>
      </p>
    </AuthLayout>
  );
}