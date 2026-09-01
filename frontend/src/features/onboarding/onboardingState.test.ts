import { describe, it, expect, beforeEach } from "vitest";
import { needsOnboarding, getOnboardingOutcome, setOnboardingOutcome } from "./onboardingState";

describe("Image-access onboarding state (first-time only, no image data)", () => {
  beforeEach(() => localStorage.clear());

  it("a new user needs onboarding", () => {
    expect(needsOnboarding("user-1")).toBe(true);
    expect(getOnboardingOutcome("user-1")).toBeNull();
  });

  it("once granted, onboarding is not shown again", () => {
    setOnboardingOutcome("user-1", "granted");
    expect(needsOnboarding("user-1")).toBe(false);
    expect(getOnboardingOutcome("user-1")).toBe("granted");
  });

  it("once skipped, onboarding is not shown again", () => {
    setOnboardingOutcome("user-2", "skipped");
    expect(needsOnboarding("user-2")).toBe(false);
    expect(getOnboardingOutcome("user-2")).toBe("skipped");
  });

  it("outcome is tracked per user and stores no image data", () => {
    setOnboardingOutcome("user-1", "granted");
    expect(needsOnboarding("user-3")).toBe(true);
    // The stored value is only the outcome marker, never image content.
    const dump = JSON.stringify({ ...localStorage });
    expect(dump).toContain("granted");
    expect(dump).not.toContain("data:image");
  });
});