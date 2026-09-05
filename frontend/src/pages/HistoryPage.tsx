import { useCallback, useEffect, useState } from "react";
import { apiService } from "../api/client";
import { isNotConnected } from "../api/errors";
import { useConversations, useDispatch } from "../hooks";
import { useChatLens } from "../hooks/useChatLens";
import { EmptyState, ErrorState, NotConnectedState } from "../components/States";
import { Icon } from "../components/Icon";
import { formatRelative } from "../utils/format";

/**
 * Search History = the user's real, backend-durable ChatLens conversations.
 *
 * This reuses the SAME persistence as the sidebar: the backend persists every
 * search/refine turn per account (chat_repo), exposed via GET /api/chats and
 * GET /api/chats/{id}. This page refreshes the list from the backend on mount
 * (so newly-created conversations show up), renders each as an openable history
 * item, and opening one restores the full transcript via the existing
 * selectConversation() flow (getChat -> CONVERSATION_HYDRATED). No fake history,
 * no duplicate store: account isolation and continuation come for free from the
 * existing conversation architecture.
 */

type HistoryStatus = "loading" | "ready" | "empty" | "notConnected" | "error";

export function HistoryPage() {
  const conversations = useConversations();
  const dispatch = useDispatch();
  const c = useChatLens();
  const [status, setStatus] = useState<HistoryStatus>("loading");
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(() => {
    let cancelled = false;
    setStatus("loading");
    apiService
      .listChats()
      .then((summaries) => {
        if (cancelled) return;
        // Keep the store in sync so the sidebar + this page agree.
        dispatch({ type: "CONVERSATIONS_LOADED", summaries });
        setStatus(summaries.length > 0 ? "ready" : "empty");
      })
      .catch((err) => {
        if (cancelled) return;
        setStatus(isNotConnected(err) ? "notConnected" : "error");
      });
    return () => {
      cancelled = true;
    };
  }, [dispatch]);

  useEffect(() => load(), [load, reloadKey]);

  if (status === "loading") {
    return (
      <div className="history-list" aria-busy="true">
        {[0, 1, 2].map((i) => (
          <div className="history-item skeleton-row" key={i}>
            <div className="sk-line" style={{ width: "60%" }} />
            <div className="sk-line" style={{ width: "30%" }} />
          </div>
        ))}
      </div>
    );
  }

  if (status === "notConnected") {
    return (
      <NotConnectedState
        title="Search history is ready"
        message="Your conversations are saved to your account. Connect the backend to load them here."
      />
    );
  }

  if (status === "error") {
    return (
      <ErrorState
        title="Couldn't load your history"
        message="We couldn't load your saved conversations right now."
        onRetry={() => setReloadKey((k) => k + 1)}
      />
    );
  }

  if (conversations.summaries.length === 0) {
    return (
      <EmptyState
        icon="history"
        title="No conversations yet"
        message="Search for a visual memory to start a conversation. Your chats are saved here automatically."
      />
    );
  }

  return (
    <div className="history-list">
      {conversations.summaries.map((s) => {
        const active = s.id === conversations.activeId;
        return (
          <button
            key={s.id}
            className={`history-item ${active ? "active" : ""}`}
            onClick={() => c.selectConversation(s.id)}
            aria-current={active ? "page" : undefined}
          >
            <span className="history-icon"><Icon name="history" size={18} /></span>
            <span className="history-main">
              <span className="history-title">{s.title || "New chat"}</span>
              {s.createdAt > 0 && <span className="history-when">{formatRelative(s.createdAt)}</span>}
            </span>
            <Icon name="search" size={16} />
          </button>
        );
      })}
    </div>
  );
}