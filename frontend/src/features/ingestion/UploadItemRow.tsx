import type { ProcessingStatus } from "../../api/types";
import type { UploadItem } from "../../state/types";
import { Icon } from "../../components/Icon";

/**
 * Backend processing stages. The client only performs the local upload; OCR,
 * understanding, semantic representation and indexing are owned by the backend.
 * When no backend is connected, these are shown as PENDING (never faked as done).
 */
const BACKEND_STAGES = ["OCR", "Understanding image", "Semantic representation", "Indexing"];

/** Map a backend-reported ProcessingStatus to how many stages are complete. */
function stagesDone(status: ProcessingStatus): number {
  switch (status) {
    case "processing": return 1;
    case "indexed": return 3;
    case "ready": return BACKEND_STAGES.length;
    default: return 0; // "uploaded" | "failed"
  }
}

export function UploadItemRow({
  item,
  onRemove,
  awaitingBackend,
}: {
  item: UploadItem;
  onRemove: (id: string) => void;
  awaitingBackend: boolean;
}) {
  const invalid = !item.validation.valid;
  const failed = item.status === "failed";
  const done = stagesDone(item.status);

  return (
    <div className="upload-item">
      <img className="upload-thumb" src={item.previewUrl} alt={item.fileName} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
          <span style={{ fontWeight: 700, color: "var(--navy)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {item.fileName}
          </span>
          <button className="icon-btn" style={{ width: 30, height: 30 }} onClick={() => onRemove(item.id)} aria-label="Remove file">
            <Icon name="close" size={15} />
          </button>
        </div>

        {invalid ? (
          <p className="card-date" style={{ color: "#ef4444", marginTop: 6 }}>{item.validation.error}</p>
        ) : failed ? (
          <p className="card-date" style={{ color: "#ef4444", marginTop: 6 }}>{item.error ?? "Upload failed."}</p>
        ) : (
          <div className="pipeline">
            <div className="pipeline-step done">
              <span className="dot"><Icon name="check" size={10} /></span>Image selected
            </div>
            {BACKEND_STAGES.map((label, i) => {
              const isDone = i < done;
              return (
                <div className={`pipeline-step ${isDone ? "done" : ""}`} key={label}>
                  <span className="dot">{isDone ? <Icon name="check" size={10} /> : null}</span>
                  {label}
                </div>
              );
            })}
            {awaitingBackend && (
              <p className="card-date" style={{ marginTop: 6 }}>
                Waiting for backend integration to run OCR, understanding and indexing.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}