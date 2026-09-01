import { useState, type InputHTMLAttributes } from "react";
import { Icon } from "../../components/Icon";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  id: string;
}

/** Labeled text input styled for the auth card. */
export function AuthField({ label, id, ...rest }: Props) {
  return (
    <div className="auth-field">
      <label htmlFor={id}>{label}</label>
      <input id={id} className="auth-input" {...rest} />
    </div>
  );
}

/** Password input with a show/hide toggle. */
export function PasswordField({ label, id, ...rest }: Props) {
  const [show, setShow] = useState(false);
  return (
    <div className="auth-field">
      <label htmlFor={id}>{label}</label>
      <div className="auth-input-wrap">
        <input id={id} className="auth-input" type={show ? "text" : "password"} {...rest} />
        <button
          type="button"
          className="auth-eye"
          onClick={() => setShow((s) => !s)}
          aria-label={show ? "Hide password" : "Show password"}
        >
          <Icon name="eye" size={18} />
        </button>
      </div>
    </div>
  );
}