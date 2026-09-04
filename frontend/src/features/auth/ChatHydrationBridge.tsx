import { useEffect, useRef, type ReactNode } from "react";
import { useAuth } from "./useAuth";
import { useDispatch } from "../../hooks/useStore";
import { apiService } from "../../api/client";
import { isNotConnected } from "../../api/errors";

/**
 * Loads the signed-in account's durable chats on login / account-ready.
 *
 * Rendered INSIDE StoreProvider (like AccountResetBridge) so it can dispatch.
 * It watches the signed-in account id (`useAuth().user?.id`). Whenever that id
 * changes to a NON-NULL value (login, session restore, or switch A -> B) it:
 *   1. Dispatches `STATE_RESET` FIRST so no prior-account chat/results linger
 *      before hydration (Account B must never briefly show A's chats). This is
 *      idempotent with the AccountResetBridge reset and guarantees ordering
 *      within this single effect.
 *   2. Calls `apiService.listChats()` and populates `conversations.summaries`
 *      with the account's durable conversations (newest first from the backend).
 *
 * It does NOT auto-open another account's chat and does NOT hydrate a full
 * transcript here — selecting a conversation hydrates it via getChat. When the
 * backend is not connected the call rejects with NotConnectedError and we leave
 * the (already reset) in-memory state empty rather than fabricating chats.
 *
 * LOGOUT (id -> null) is intentionally NOT handled here: it must clear in-memory
 * state (via AccountResetBridge / clearAccountId) but MUST NOT touch the backend.
 */
export function ChatHydrationBridge({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const dispatch = useDispatch();
  const prevId = useRef<string | null | undefined>(undefined);

  useEffect(() => {
    const current = user?.id ?? null;
    if (prevId.current === current) return;
    prevId.current = current;
    if (!current) return; // logout / signed out: never load or delete.

    let cancelled = false;
    // Reset in-memory slices BEFORE hydrating so A's chats can't leak into B.
    dispatch({ type: "STATE_RESET" });
    void (async () => {
      try {
        const summaries = await apiService.listChats();
        if (cancelled) return;
        dispatch({ type: "CONVERSATIONS_LOADED", summaries });
      } catch (err) {
        // NotConnected / failure: leave the reset (empty) state; never fabricate.
        if (!isNotConnected(err)) {
          // Non-connection errors are swallowed here; the user simply starts
          // with no listed chats until a successful load. No fake history.
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user?.id, dispatch]);

  return <>{children}</>;
}
