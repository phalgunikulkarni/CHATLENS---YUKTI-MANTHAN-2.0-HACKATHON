/**
 * First-time image-access onboarding state.
 *
 * This tracks ONLY whether the user has completed (or dismissed) the onboarding
 * step - it is kept completely separate from actual image data, and it never
 * fabricates images or memories. Persisted per-user so the modal appears once
 * during first-time onboarding and not on every navigation.
 */

const KEY_PREFIX = "chatlens.onboarding.imageAccess.v1";

export type OnboardingOutcome = "granted" | "skipped";

function keyFor(userId: string | undefined): string {
  return `${KEY_PREFIX}:${userId ?? "anon"}`;
}

export function getOnboardingOutcome(userId: string | undefined): OnboardingOutcome | null {
  try {
    const raw = localStorage.getItem(keyFor(userId));
    return raw === "granted" || raw === "skipped" ? raw : null;
  } catch {
    return null;
  }
}

export function setOnboardingOutcome(userId: string | undefined, outcome: OnboardingOutcome): void {
  try {
    localStorage.setItem(keyFor(userId), outcome);
  } catch {
    // Storage may be unavailable; onboarding will simply show again next load.
  }
}

/** Whether the first-time onboarding modal should be shown for this user. */
export function needsOnboarding(userId: string | undefined): boolean {
  return getOnboardingOutcome(userId) === null;
}