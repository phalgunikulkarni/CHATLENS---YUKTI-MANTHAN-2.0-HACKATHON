import { useEffect } from "react";
import { Icon } from "../../components/Icon";

/** Centered success popup shown briefly after login or signup. */
export function SuccessPopup({
  mode,
  name,
  onDone,
}: {
  mode: "login" | "signup";
  name?: string;
  onDone: () => void;
}) {
  useEffect(() => {
    const t = setTimeout(onDone, 1600);
    return () => clearTimeout(t);
  }, [onDone]);

  const first = name ? name.split(" ")[0] : "";
  const heading =
    mode === "signup"
      ? `Welcome to ChatLens${first ? `, ${first}` : ""}!`
      : `Welcome back${first ? `, ${first}` : ""}!`;
  const body =
    mode === "signup"
      ? "Your account has been created."
      : "You have successfully signed in to ChatLens.";

  return (
    <div className="dialog-wrap" role="alertdialog" aria-modal="true" aria-label="Success">
      <div className="success-popup">
        <div className="success-check"><Icon name="check" size={34} /></div>
        <h3>{heading}</h3>
        <p>{body}</p>
        <div className="success-sub">
          <span className="typing"><span /><span /><span /></span>
          Opening your memories...
        </div>
      </div>
    </div>
  );
}
