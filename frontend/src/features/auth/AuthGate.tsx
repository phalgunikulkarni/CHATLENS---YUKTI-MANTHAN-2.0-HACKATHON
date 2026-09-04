import { useEffect, useState } from "react";
import { useAuth } from "./useAuth";
import { LoginPage } from "./LoginPage";
import { SignupPage } from "./SignupPage";
import { SuccessPopup } from "./SuccessPopup";

/**
 * Renders the auth experience for unauthenticated users and a brief success
 * popup on transition to authenticated. Once authenticated (and the popup has
 * finished), it renders the protected app passed as children.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [showSuccess, setShowSuccess] = useState(false);
  const [successMode, setSuccessMode] = useState<"login" | "signup">("login");
  const [wasAuthed, setWasAuthed] = useState(isAuthenticated);

  // Show the success popup only on the unauth -> auth transition (not on reload
  // restore, which starts already authenticated). Capture the last-used form so
  // the popup reflects whether the user logged in or signed up.
  //
  // On the auth -> unauth transition (logout), reset the transient UI state so
  // the user always returns to the SIGN-IN page (even if they had reached the
  // app via the Signup flow) and no stale success popup remains queued.
  useEffect(() => {
    if (isAuthenticated && !wasAuthed) {
      setSuccessMode(mode);
      setShowSuccess(true);
    } else if (!isAuthenticated && wasAuthed) {
      setShowSuccess(false);
      setMode("login");
    }
    setWasAuthed(isAuthenticated);
  }, [isAuthenticated, wasAuthed, mode]);

  if (isAuthenticated) {
    return (
      <>
        {children}
        {showSuccess && <SuccessPopup mode={successMode} name={user?.name} onDone={() => setShowSuccess(false)} />}
      </>
    );
  }

  return mode === "login" ? (
    <LoginPage onGoToSignup={() => setMode("signup")} />
  ) : (
    <SignupPage onGoToLogin={() => setMode("login")} />
  );
}