import { useRef, useState, type DragEvent } from "react";
import { Icon } from "../../components/Icon";

interface Props {
  onFiles: (files: File[]) => void;
}

/** Drag-and-drop + file-picker upload zone. Multiple files supported. */
export function UploadZone({ onFiles }: Props) {
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    onFiles(Array.from(e.dataTransfer.files));
  };

  return (
    <div
      className={`dropzone ${drag ? "drag" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={handleDrop}
    >
      <div className="state-icon" style={{ margin: "0 auto 14px" }}><Icon name="upload" size={30} /></div>
      <h3 style={{ color: "var(--navy)", marginBottom: 6 }}>Drop images to remember them</h3>
      <p className="card-desc" style={{ maxWidth: 380, margin: "0 auto 16px" }}>
        Screenshots, notes, receipts, slides and more. PNG, JPEG, WEBP or GIF up to 10 MB.
      </p>
      <button className="btn btn-primary" onClick={() => inputRef.current?.click()}>
        <Icon name="image" size={16} /> Browse files
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(e) => { if (e.target.files) onFiles(Array.from(e.target.files)); e.target.value = ""; }}
      />
    </div>
  );
}
