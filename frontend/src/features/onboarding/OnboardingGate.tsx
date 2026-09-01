import { useState, type ReactNode } from "react";
import { useAuth } from "../auth/useAuth";
import { useChatLens } from "../../hooks/useChatLens";
import { useDispatch } from "../../hooks";
import { PermissionModal } from "./PermissionModal";
import { needsOnboarding, setOnboardingOutcome } from "./onboardingState";

/**
 * First-time image-access onboarding. Sits INSIDE the store so it can queue the
 * user's chosen images through the existing ingestion flow. Shows the permission
 * modal only once per user (tracked separately from image data). Renders the
 * dashboard (children) once onboarding is resolved.
 */
export function OnboardingGate({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const c = useChatLens();
  const dispatch = useDispatch();
  // Snapshot the "needs onboarding" decision once, so navigation never re-opens it.
  const [showModal, setShowModal] = useState(() => needsOnboarding(user?.id));

  const handleAllow = (files: File[]) => {
    // Only files the user explicitly chose. Reuses the existing ingestion flow;
    // no fake memories are created.
    if (files.length > 0) c.queueFiles(files);
    setOnboardingOutcome(user?.id, "granted");
    dispatch({ type: "IMAGE_REMINDER_SET", show: false });
  };

  const handleSkip = () => {
    setOnboardingOutcome(user?.id, "skipped");
    // Non-intrusive dashboard reminder to add images later.
    dispatch({ type: "IMAGE_REMINDER_SET", show: true });
    setShowModal(false);
  };

  return (
    <>
      {children}
      {showModal && (
        <PermissionModal
          onAllow={handleAllow}
          onSkip={handleSkip}
          onComplete={() => setShowModal(false)}
        />
      )}
    </>
  );
}