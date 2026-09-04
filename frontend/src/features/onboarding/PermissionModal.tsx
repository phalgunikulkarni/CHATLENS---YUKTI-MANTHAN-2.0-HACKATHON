import { useEffect, useRef, useState } from "react";
import { useFocusTrap } from "../../hooks";
import { Icon } from "../../components/Icon";
import { apiService, IS_BACKEND_CONNECTED } from "../../api/client";
import { isNotConnected } from "../../api/errors";
import type { AccessStatus } from "../../api/types";

type Phase = "intro" | "processing" | "done";

interface Props {
  /** Called when the user grants ChatLens access to their image folders. */
  onAllow: () => void;
  /** Called when the user chooses "Not now". */
  onSkip: () => void;
  /** Called once the flow completes and the dashboard should open. */
  onComplete: () => void;
}

const BENEFITS = [
  "Find screenshots, notes and documents",
  "Understand text inside images",
  "Search memories using natural language",
  "Organize your visual memory library",
];

/** Honest access-setup steps - these reflect backend-reported status only. */
const STEPS = [
  "Access granted",
  "Preparing memories",
  "Reading image content",
  "Creating searchable representation",
];

/** How often we poll the backend for indexing status. */
const POLL_INTERVAL_MS = 1500;

/**
 * First-time image-access onboarding modal.
 *
 * ChatLens only works with the folders the user authorizes - it never silently
 * scans the device. "Grant Access" asks the ChatLens backend to open a native
 * folder picker and begin indexing; this modal then reflects the backend's real
 * authorization and indexing status. It never fabricates progress percentages
 * or claims indexing is done before the backend reports "ready".
 */
export function PermissionModal({ onAllow, onSkip, onComplete }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [phase, setPhase] = useState<Phase>("intro");
  const [error, setError] = useState<string | null>(null);
  const [granting, setGranting] = useState(false);
  const [indexing, setIndexing] = useState<AccessStatus["indexing"]>("idle");
  useFocusTrap(ref, true, phase === "intro" ? onSkip : undefined);

  // In the "done" phase, auto-advance to the dashboard after a short delay.
  useEffect(() => {
    if (phase !== "done") return;
    const t = setTimeout(onComplete, 1600);
    return () => clearTimeout(t);
  }, [phase, onComplete]);

  // Poll backend indexing status while in the processing phase. Cleans up on
  // unmount and whenever we leave the processing phase so polling never leaks.
  useEffect(() => {
    if (phase !== "processing") return;

    let aborted = false;

    const poll = async () => {
      try {
        const status = await apiService.getAccessStatus();
        if (aborted) return;
        setIndexing(status.indexing);
        if (status.indexing === "ready") {
          aborted = true;
          clearInterval(timer);
          // Only now do we record the completion marker via onAllow().
          onAllow();
          setPhase("done");
        } else if (status.indexing === "failed") {
          aborted = true;
          clearInterval(timer);
          setError(`Indexing failed: ${status.error ?? "unknown error"}`);
          setPhase("intro");
        }
      } catch (err) {
        if (aborted) return;
        aborted = true;
        clearInterval(timer);
        setError(
          isNotConnected(err)
            ? "ChatLens backend is not connected."
            : "Could not check indexing status. Please try again.",
        );
        setPhase("intro");
      }
    };

    const timer = setInterval(poll, POLL_INTERVAL_MS);
    // Kick off an immediate poll so the UI reflects status without waiting.
    void poll();

    return () => {
      aborted = true;
      clearInterval(timer);
    };
  }, [phase, onAllow]);

  const grantAccess = async () => {
    if (granting) return;
    setError(null);
    setGranting(true);
    try {
      const result = await apiService.grantAccess();
      if (!result.authorized) {
        // e.g. "No folder selected." / "could not be authorized." - stay on intro.
        setError(result.message);
        return;
      }
      // Authorized: move to processing and let the poller drive completion.
      setIndexing("running");
      setPhase("processing");
    } catch (err) {
      setError(
        isNotConnected(err)
          ? "ChatLens backend is not connected."
          : "Could not start folder access. Please try again.",
      );
      // Stay on intro; do NOT claim success.
    } finally {
      setGranting(false);
    }
  };

  return (
    <div className="dialog-wrap" role="dialog" aria-modal="true" aria-labelledby="perm-title">
      <div className="permission-modal" ref={ref}>
        {phase === "intro" && (
          <>
            <div className="perm-illustration" aria-hidden="true">
              <Icon name="image" size={34} />
              <span className="perm-illustration-badge"><Icon name="sparkles" size={14} /></span>
            </div>
            <h2 id="perm-title" className="perm-title">Let ChatLens access your image folders</h2>
            <p className="perm-sub">
              ChatLens needs permission to access your existing image folders so it can understand, organize, and search your visual memories.
            </p>

            <ul className="perm-benefits">
              {BENEFITS.map((b) => (
                <li key={b}><Icon name="check" size={15} /> {b}</li>
              ))}
            </ul>

            <div className="perm-privacy">
              <Icon name="eye" size={16} />
              <div>
                <strong>Your memories stay under your control.</strong>
                <p>Choose what you want ChatLens to access. You can manage connected sources and permissions later.</p>
              </div>
            </div>

            {error && (
              <p className="perm-note" role="alert" style={{ color: "var(--danger, #d64545)", marginTop: 4 }}>
                <Icon name="wifi-off" size={14} /> {error}
              </p>
            )}

            <div className="perm-actions">
              <button className="btn btn-ghost" onClick={onSkip} disabled={granting}>Not now</button>
              <button className="btn btn-primary perm-allow" onClick={grantAccess} disabled={granting}>
                <Icon name="image" size={16} /> {granting ? "Opening..." : "Grant Access"}
              </button>
            </div>
            <p className="perm-note">ChatLens will only access the folders you authorize.</p>
          </>
        )}

        {phase === "processing" && (
          <div className="perm-processing">
            <h2 className="perm-title">Setting up access</h2>
            <div className="pipeline" style={{ marginTop: 18, textAlign: "left" }}>
              {STEPS.map((label, i) => {
                const done = i === 0; // "Access granted" is confirmed once we reach processing.
                const active = i > 0; // Indexing steps are in progress while the backend works.
                return (
                  <div className={`pipeline-step ${done ? "done" : active ? "active" : ""}`} key={label}>
                    <span className="dot">
                      {done ? <Icon name="check" size={10} /> : active ? <Icon name="sparkles" size={10} className="spin" /> : null}
                    </span>
                    {label}
                  </div>
                );
              })}
            </div>
            <p className="perm-note" style={{ marginTop: 14 }} aria-live="polite">
              {indexing === "running"
                ? "Indexing your folders..."
                : "Setting up folder access..."}
            </p>
            {!IS_BACKEND_CONNECTED && (
              <p className="perm-note" style={{ marginTop: 8 }}>
                Reading content and building searchable representations run on the ChatLens backend once connected.
              </p>
            )}
          </div>
        )}

        {phase === "done" && (
          <div className="perm-done">
            <div className="success-check"><Icon name="check" size={34} /></div>
            <h2 className="perm-title">You&apos;re all set!</h2>
            <p className="perm-sub">
              ChatLens can now search the folders you authorized.
            </p>
            <div className="success-sub">
              <span className="typing"><span /><span /><span /></span>
              Opening ChatLens...
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
