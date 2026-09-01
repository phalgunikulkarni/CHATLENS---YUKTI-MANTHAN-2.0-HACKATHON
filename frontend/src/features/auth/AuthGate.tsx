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
  const [wasAuthed, setWasAuthed] = useState(isAuthenticated);

  // Show the success popup only on the unauth -> auth transition (not on reload
  // restore, which starts already authenticated).
  useEffect(() => {
    if (isAuthenticated && !wasAuthed) {
      setShowSuccess(true);
    }
    setWasAuthed(isAuthenticated);
  }, [isAuthenticated, wasAuthed]);

  if (isAuthenticated) {
    return (
      <>
        {children}
        {showSuccess && <SuccessPopup name={user?.name} onDone={() => setShowSuccess(false)} />}
      </>
    );
  }

  return mode === "login" ? (
    <LoginPage onGoToSignup={() => setMode("signup")} />
  ) : (
    <SignupPage onGoToLogin={() => setMode("login")} />
  );
}