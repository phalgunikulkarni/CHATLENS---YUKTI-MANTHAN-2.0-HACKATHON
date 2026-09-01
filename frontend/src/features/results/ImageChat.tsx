import { useEffect, useRef, useState } from "react";
import { apiService } from "../../api/client";
import { isNotConnected } from "../../api/errors";
import { isSendable } from "../../utils/validation";
import { IS_DEMO_MODE } from "../../api/client";
import { Icon } from "../../components/Icon";

interface Turn {
  role: "user" | "assistant";
  text: string;
}

/**
 * Conversational Q&A scoped to a single image. Retains the per-image
 * conversation context and sends it with each question. Uses the API service
 * (mock/backend) - never presents mock answers as real; demo answers are labeled.
 */
export function ImageChat({ imageId }: { imageId: string }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [notConnected, setNotConnected] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  // Reset the conversation whenever a different image is opened.
  useEffect(() => {
    setTurns([]);
    setNotConnected(false);
    setDraft("");
  }, [imageId]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, busy]);

  const ask = async () => {
    if (!isSendable(draft) || busy) return;
    const question = draft.trim();
    const history = turns.map((t) => ({ role: t.role, text: t.text }));
    setTurns((t) => [...t, { role: "user", text: question }]);
    setDraft("");
    setBusy(true);
    setNotConnected(false);
    try {
      const res = await apiService.askAboutImage({ imageId, question, history });
      setTurns((t) => [...t, { role: "assistant", text: res.answer }]);
    } catch (err) {
      if (isNotConnected(err)) {
        setNotConnected(true);
      } else {
        setTurns((t) => [...t, { role: "assistant", text: "Sorry, I could not answer that right now." }]);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="image-chat">
      <div className="section-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Icon name="brain" size={16} style={{ color: "var(--accent)" }} /> Ask about this image
        {IS_DEMO_MODE && <span className="demo-tag">Demo answers</span>}
      </div>

      {turns.length > 0 && (
        <div className="image-chat-log" role="log" aria-live="polite" ref={listRef}>
          {turns.map((t, i) => (
            <div className={`msg ${t.role === "user" ? "user" : "agent"}`} key={i}>{t.text}</div>
          ))}
          {busy && <div className="msg agent"><span className="typing"><span /><span /><span /></span></div>}
        </div>
      )}

      {notConnected && (
        <p className="explanation-empty">Image Q&A needs the ChatLens backend. Connect it to ask questions.</p>
      )}

      <div className="composer" style={{ border: "none", padding: "10px 0 0" }}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") ask(); }}
          placeholder='e.g. "What is this error?"'
          aria-label="Ask about this image"
        />
        <button className="btn btn-primary" onClick={ask} disabled={!isSendable(draft) || busy} aria-label="Send question">
          <Icon name="arrow" size={18} />
        </button>
      </div>
    </div>
  );
}