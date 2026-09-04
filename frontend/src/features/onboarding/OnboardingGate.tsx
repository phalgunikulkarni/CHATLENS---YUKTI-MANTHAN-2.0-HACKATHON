import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "../auth/useAuth";
import { apiService } from "../../api/client";
import { PermissionModal } from "./PermissionModal";
import { needsOnboarding, setOnboardingOutcome } from "./onboardingState";

type Decision = "pending" | "show" | "hide";

/**
 * First-time image-access onboarding. Records whether the user has granted (or
 * skipped) access to their image folders and shows the permission modal only
 * once per user (tracked separately from any image data - it never fabricates
 * memories). Renders the dashboard (children) once onboarding is resolved.
 *
 * The local per-user marker is authoritative when present. When it is missing
 * (e.g. a fresh device/browser), we consult the backend's access status once as
 * a fallback: if the backend reports access already authorized and indexing
 * ready, onboarding is treated as complete and the local marker is restored for
 * the current stable user id. Any error / not-connected state falls back to the
 * normal onboarding flow - it never blocks the app and never fabricates access.
 */
export function OnboardingGate({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  // Snapshot the "needs onboarding" decision once, so navigation never re-opens
  // it. If the local marker exists -> hide immediately (no network). If it is
  // missing -> pending, and consult the backend once in the effect below.
  const [decision, setDecision] = useState<Decision>(() =>
    needsOnboarding(user?.id) ? "pending" : "hide",
  );

  useEffect(() => {
    if (decision !== "pending") return;
    let cancelled = false;

    (async () => {
      try {
        const status = await apiService.getAccessStatus();
        if (cancelled) return;
        if (status.authorized === true && status.indexing === "ready") {
          // Backend confirms access is already set up: restore the local marker
          // for the CURRENT stable user id and treat onboarding as complete.
          setOnboardingOutcome(user?.id, "granted");
          setDecision("hide");
        } else {
          setDecision("show");
        }
      } catch {
        // Not connected / error: fall back to normal onboarding. Never block,
        // never fabricate access.
        if (!cancelled) setDecision("show");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [decision, user?.id]);

  const handleAllow = () => {
    // Record that the user granted access to their image folders. Actual folder
    // access/indexing is owned by the backend; no memories are created here.
    setOnboardingOutcome(user?.id, "granted");
  };

  const handleSkip = () => {
    setOnboardingOutcome(user?.id, "skipped");
    setDecision("hide");
  };

  return (
    <>
      {children}
      {decision === "show" && (
        <PermissionModal
          onAllow={handleAllow}
          onSkip={handleSkip}
          onComplete={() => setDecision("hide")}
        />
      )}
    </>
  );
}
