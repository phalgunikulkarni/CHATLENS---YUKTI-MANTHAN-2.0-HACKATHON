import { useEffect } from "react";
import { Icon } from "../../components/Icon";

/** Centered success popup shown briefly after login/registration. */
export function SuccessPopup({ name, onDone }: { name?: string; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 1600);
    return () => clearTimeout(t);
  }, [onDone]);

  return (
    <div className="dialog-wrap" role="alertdialog" aria-modal="true" aria-label="Login successful">
      <div className="success-popup">
        <div className="success-check"><Icon name="check" size={34} /></div>
        <h3>Welcome back{name ? `, ${name.split(" ")[0]}` : ""}!</h3>
        <p>You have successfully signed in to ChatLens.</p>
        <div className="success-sub">
          <span className="typing"><span /><span /><span /></span>
          Opening your memories...
        </div>
      </div>
    </div>
  );
}