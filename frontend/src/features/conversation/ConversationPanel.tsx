import { useEffect, useRef, useState } from "react";
import { useConversation } from "../../hooks";
import { isSendable } from "../../utils/validation";
import { Icon } from "../../components/Icon";

interface Props {
  onSend: (message: string) => void;
}

/**
 * Conversational refinement panel. Preserves transcript order, announces agent
 * turns via an ARIA live region, shows a refining indicator, and rejects
 * whitespace-only submissions.
 */
export function ConversationPanel({ onSend }: Props) {
  const { messages, activeClues, turnInProgress, intentError } = useConversation();
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, turnInProgress]);

  const submit = () => {
    if (!isSendable(draft)) return;
    onSend(draft.trim());
    setDraft("");
  };

  return (
    <div className="panel conversation">
      <div className="panel-head">
        <Icon name="brain" size={18} style={{ color: "var(--accent)" }} />
        <h3>Refine conversationally</h3>
      </div>

      <div className="messages" role="log" aria-live="polite" aria-label="Conversation" ref={listRef}>
        {messages.length === 0 && (
          <div className="msg agent">
            Ask me to find a memory, then add clues like "it was handwritten" to refine.
          </div>
        )}
        {messages.map((m) => (
          <div className={`msg ${m.role}`} key={m.id}>
            {m.role === "agent" && m.intent && <span className="intent-tag">{m.intent}</span>}
            {m.text}
          </div>
        ))}
        {turnInProgress && (
          <div className="msg agent">
            <span className="typing"><span /><span /><span /></span>
          </div>
        )}
        {intentError && (
          <div className="msg agent" role="alert" style={{ color: "#b91c1c" }}>
            I could not interpret that response. Please try rephrasing.
          </div>
        )}
      </div>

      {activeClues.length > 0 && (
        <div className="refine-strip">
          <Icon name="tag" size={14} />
          Memory clues: {activeClues.map((c) => c.label).join(" - ")}
        </div>
      )}

      <div className="composer">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
          placeholder='e.g. "No, they were handwritten"'
          aria-label="Refine your search"
        />
        <button className="btn btn-primary" onClick={submit} disabled={!isSendable(draft) || turnInProgress} aria-label="Send refinement">
          <Icon name="arrow" size={18} />
        </button>
      </div>
    </div>
  );
}
