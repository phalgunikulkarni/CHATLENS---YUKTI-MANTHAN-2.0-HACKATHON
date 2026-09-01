import { useEffect, useRef, useState } from "react";
import { useFocusTrap } from "../../hooks";
import { Icon } from "../../components/Icon";
import { IS_BACKEND_CONNECTED } from "../../api/client";

type Phase = "intro" | "processing" | "done";

interface Props {
  /** Called with the images the user explicitly chose (may be empty if they
   *  allow access but pick nothing). Should queue them via the ingestion flow. */
  onAllow: (files: File[]) => void;
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

/** Honest processing steps - these are pending until a backend reports status. */
const STEPS = [
  "Images selected",
  "Preparing memories",
  "Reading image content",
  "Creating searchable representation",
];

/**
 * First-time image-access onboarding modal.
 *
 * ChatLens can only work with files the user EXPLICITLY chooses - it never
 * silently accesses the device gallery. "Allow access" opens the native image
 * file picker (PNG/JPG/JPEG/WEBP, multiple allowed). No camera/mic/location.
 */
export function PermissionModal({ onAllow, onSkip, onComplete }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>("intro");
  const [selectedCount, setSelectedCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  useFocusTrap(ref, true, phase === "intro" ? onSkip : undefined);

  // In the "done" phase, auto-advance to the dashboard after a short delay.
  useEffect(() => {
    if (phase !== "done") return;
    const t = setTimeout(onComplete, 1600);
    return () => clearTimeout(t);
  }, [phase, onComplete]);

  const openPicker = () => {
    setError(null);
    inputRef.current?.click();
  };

  const handleFiles = (fileList: FileList | null) => {
    const files = fileList ? Array.from(fileList) : [];
    // The user may allow access but select nothing - that's still "granted".
    setSelectedCount(files.length);
    onAllow(files);
    setPhase("processing");
    // Brief client-side "preparing" moment, then land on the success state.
    // We do NOT claim OCR/embeddings/indexing ran - the backend owns that.
    setTimeout(() => setPhase("done"), 1100);
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
            <h2 id="perm-title" className="perm-title">Let ChatLens find your memories</h2>
            <p className="perm-sub">
              ChatLens needs access to your images to understand, organize, and search your visual memories.
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

            {error && <p className="perm-error" role="alert">{error}</p>}

            <div className="perm-actions">
              <button className="btn btn-ghost" onClick={onSkip}>Not now</button>
              <button className="btn btn-primary perm-allow" onClick={openPicker}>
                <Icon name="image" size={16} /> Allow access
              </button>
            </div>
            <p className="perm-note">You will choose the images to add. ChatLens never opens your gallery on its own.</p>

            <input
              ref={inputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              multiple
              hidden
              onChange={(e) => handleFiles(e.target.files)}
            />
          </>
        )}

        {phase === "processing" && (
          <div className="perm-processing">
            <h2 className="perm-title">Preparing your memories</h2>
            <div className="pipeline" style={{ marginTop: 18, textAlign: "left" }}>
              {STEPS.map((label, i) => {
                const done = i === 0; // only "Images selected" is truly done client-side
                const active = i === 1;
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
            {!IS_BACKEND_CONNECTED && (
              <p className="perm-note" style={{ marginTop: 14 }}>
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
              {selectedCount > 0
                ? "ChatLens can now work with the images you chose to add."
                : "ChatLens can now work with the images you choose to add."}
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