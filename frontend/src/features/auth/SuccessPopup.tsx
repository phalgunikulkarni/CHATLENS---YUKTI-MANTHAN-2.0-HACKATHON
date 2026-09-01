import { useEffect, useRef } from "react";
import { useFocusTrap } from "../../hooks";
import { Icon } from "../../components/Icon";

/**
 * Centered success popup shown after a successful (frontend demo) sign-in.
 * Requires an explicit "Continue" click, which then advances to image-access
 * onboarding. Focus-trapped and keyboard accessible.
 */
export function SuccessPopup({ name, onContinue }: { name?: string; onContinue: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, true);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Enter") onContinue(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onContinue]);

  return (
    <div className="dialog-wrap" role="alertdialog" aria-modal="true" aria-labelledby="signin-success-title">
      <div className="success-popup" ref={ref}>
        <div className="success-check"><Icon name="check" size={34} /></div>
        <h3 id="signin-success-title">You&apos;re successfully signed in!</h3>
        <p>
          Welcome back{name ? `, ${name.split(" ")[0]}` : ""} to ChatLens. Your visual memory
          workspace is ready.
        </p>
        <button className="btn btn-primary" style={{ marginTop: 20, minWidth: 160 }} onClick={onContinue} autoFocus>
          Continue
        </button>
      </div>
    </div>
  );
}