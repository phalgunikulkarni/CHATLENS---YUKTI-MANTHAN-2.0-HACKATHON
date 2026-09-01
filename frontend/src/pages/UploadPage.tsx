import { useIngestion } from "../hooks";
import { useChatLens } from "../hooks/useChatLens";
import { UploadZone } from "../features/ingestion/UploadZone";
import { UploadItemRow } from "../features/ingestion/UploadItemRow";
import { EmptyState, NotConnectedState } from "../components/States";
import { IS_BACKEND_CONNECTED } from "../api/client";

export function UploadPage() {
  const { queue } = useIngestion();
  const c = useChatLens();
  const hasValid = queue.some((it) => it.validation.valid);

  return (
    <div style={{ maxWidth: 720 }}>
      <UploadZone onFiles={c.queueFiles} />

      <div style={{ marginTop: 26 }}>
        <div className="section-title">Your uploads</div>
        {queue.length === 0 ? (
          <EmptyState
            icon="upload"
            title="Nothing uploaded yet"
            message="Drop or browse images above to add them to your visual memory."
          />
        ) : (
          <>
            {queue.map((item) => (
              <UploadItemRow
                key={item.id}
                item={item}
                onRemove={c.removeUpload}
                awaitingBackend={!IS_BACKEND_CONNECTED}
              />
            ))}
            {hasValid && !IS_BACKEND_CONNECTED && (
              <div style={{ marginTop: 16 }}>
                <NotConnectedState
                  title="Processing pipeline waiting for backend"
                  message="Your images are ready to upload. OCR, image understanding, semantic representation and indexing run on the ChatLens backend once it is connected."
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}