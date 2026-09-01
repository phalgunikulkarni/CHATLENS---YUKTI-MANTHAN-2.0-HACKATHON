import { useEffect, useState } from "react";
import { useAuth } from "./useAuth";
import { LoginPage } from "./LoginPage";
import { SignupPage } from "./SignupPage";
import { SuccessPopup } from "./SuccessPopup";

/**
 * Auth entry point:
 *   - Unauthenticated  -> login / signup pages.
 *   - Fresh sign-in    -> success popup (with Continue) shown INSTEAD of the app,
 *                         so image-access onboarding (inside children) only mounts
 *                         after the user clicks Continue. No modal overlap.
 *   - Restored session -> render the app directly (no success popup on reload).
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [celebrating, setCelebrating] = useState(false);
  const [wasAuthed, setWasAuthed] = useState(isAuthenticated);

  // Detect the unauth -> auth transition (a fresh sign-in this session).
  useEffect(() => {
    if (isAuthenticated && !wasAuthed) setCelebrating(true);
    setWasAuthed(isAuthenticated);
  }, [isAuthenticated, wasAuthed]);

  if (!isAuthenticated) {
    return mode === "login" ? (
      <LoginPage onGoToSignup={() => setMode("signup")} />
    ) : (
      <SignupPage onGoToLogin={() => setMode("login")} />
    );
  }

  // Authenticated. Hold the app behind the success popup until "Continue".
  if (celebrating) {
    return <SuccessPopup name={user?.name} onContinue={() => setCelebrating(false)} />;
  }

  return <>{children}</>;
}