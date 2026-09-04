import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/**
 * Feature: account-scoped-chat-and-isolation (Phase C, task 3.6).
 * Hydration across refresh/login and account isolation:
 *  - listChats populates conversations.summaries on login/account-ready.
 *  - getChat hydrates a selected conversation's transcript.
 *  - logout preserves the backend (NO deleteChat call) and clears in-memory.
 *  - A login -> new chat -> logout -> B login shows only B's chats (no leakage)
 *    -> A login again restores A's chats.
 *  - every request carries the account identity.
 * Validates: Requirements R7.1, R7.3 (and R1.1 via account identity).
 */

// ---- Mocked API client. listChats is account-aware (reads the holder). ----
// Each request's result is derived from the LIVE account holder so isolation is
// provable without importing any internal id helper: account A can only ever
// see chats tagged with A's id, and B only B's. This also asserts the account
// identity is present on every list request.
const { deleteChat, getChat, createChat } = vi.hoisted(() => ({
  deleteChat: vi.fn(async () => {}),
  getChat: vi.fn(),
  createChat: vi.fn(async () => ({ sessionId: "new", title: "", createdAt: null, updatedAt: null })),
}));

vi.mock("../api/client", () => {
  return {
    apiService: {
      async listChats() {
        const { getAccountId } = await import("../api/accountContext");
        const id = getAccountId();
        if (!id) throw new Error("no account"); // no identity -> no data
        return [{ sessionId: `${id}:chat-1`, title: `${id} only`, createdAt: null, updatedAt: null }];
      },
      getChat,
      deleteChat,
      createChat,
      renameChat: vi.fn(async () => ({ sessionId: "x" })),
      search: vi.fn(),
      refine: vi.fn(),
    },
  };
});

import { rootReducer, initialRootState, StoreProvider } from "../state/store";
import { conversationReducer, initialConversationState } from "../state/conversation.slice";
import { AuthProvider } from "../features/auth/AuthContext";
import { AccountResetBridge } from "../features/auth/AccountResetBridge";
import { ChatHydrationBridge } from "../features/auth/ChatHydrationBridge";
import { useAuth } from "../features/auth/useAuth";
import { useConversations } from "../hooks/useStore";
import { getAccountId } from "../api/accountContext";

const CREDS_A = { email: "a.user@example.com", password: "password1", remember: true };
const CREDS_B = { email: "b.user@example.com", password: "password1", remember: true };

describe("CONVERSATIONS_LOADED reducer (list -> summaries)", () => {
  it("maps backend summaries to summaries keyed by canonical sessionId, activeId null", () => {
    const next = rootReducer(initialRootState, {
      type: "CONVERSATIONS_LOADED",
      summaries: [
        { sessionId: "s-2", title: "Second", createdAt: "2024-01-02T00:00:00Z" },
        { sessionId: "s-1", title: "First", createdAt: "2024-01-01T00:00:00Z" },
      ],
    });
    expect(next.conversations.summaries.map((s) => s.id)).toEqual(["s-2", "s-1"]);
    expect(next.conversations.summaries[0].title).toBe("Second");
    expect(next.conversations.activeId).toBeNull();
    expect(next.conversations.snapshots).toEqual({});
  });
});

describe("CONVERSATION_HYDRATED (getChat -> transcript)", () => {
  it("replaces the transcript with persisted messages mapped to transcript roles", () => {
    const next = conversationReducer(initialConversationState, {
      type: "CONVERSATION_HYDRATED",
      sessionId: "s-9",
      messages: [
        { id: "m1", role: "user", text: "find osi notes" },
        { id: "m2", role: "agent", text: "here are 3" },
      ],
      activeClues: [],
    });
    expect(next.sessionId).toBe("s-9");
    expect(next.messages).toHaveLength(2);
    expect(next.messages[0]).toMatchObject({ role: "user", text: "find osi notes" });
    expect(next.messages[1]).toMatchObject({ role: "agent", text: "here are 3" });
  });
});

// ---- Full account-switch isolation via the ChatHydrationBridge ----

function Harness() {
  const { user, login, logout } = useAuth();
  const conversations = useConversations();
  return (
    <div>
      <button onClick={() => login(CREDS_A)}>login-a</button>
      <button onClick={() => login(CREDS_B)}>login-b</button>
      <button onClick={() => logout()}>logout</button>
      <div data-testid="uid">{user?.id ?? ""}</div>
      <div data-testid="ids">{conversations.summaries.map((s) => s.id).join(",")}</div>
    </div>
  );
}

function renderApp() {
  return render(
    <AuthProvider>
      <StoreProvider>
        <AccountResetBridge>
          <ChatHydrationBridge>
            <Harness />
          </ChatHydrationBridge>
        </AccountResetBridge>
      </StoreProvider>
    </AuthProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  deleteChat.mockClear();
  getChat.mockReset();
  createChat.mockClear();
});

afterEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  vi.clearAllMocks();
});

describe("account isolation + logout preserves backend", () => {
  it("A login shows only A's chats; B login shows only B's; A again restores A's", async () => {
    const user = userEvent.setup();
    renderApp();

    // Login A -> only A's chats loaded (chat id is tagged with A's account id).
    await user.click(screen.getByText("login-a"));
    await waitFor(() => expect(screen.getByTestId("uid").textContent).toMatch(/^acct-/), { timeout: 4000 });
    const idA = getAccountId()!;
    await waitFor(() => expect(screen.getByTestId("ids").textContent).toBe(`${idA}:chat-1`), { timeout: 4000 });

    // Switch to B -> A's chats gone, only B's shown (no leakage via store/cache).
    await user.click(screen.getByText("login-b"));
    await waitFor(() => expect(getAccountId()).not.toBe(idA), { timeout: 4000 });
    const idB = getAccountId()!;
    expect(idB).not.toBe(idA);
    await waitFor(() => expect(screen.getByTestId("ids").textContent).toBe(`${idB}:chat-1`), { timeout: 4000 });
    // No A leakage: A's tagged id must not appear anywhere in B's list.
    expect(screen.getByTestId("ids").textContent).not.toContain(idA);

    // Logout must NOT delete any backend chat, and must clear in-memory list.
    await user.click(screen.getByText("logout"));
    await waitFor(() => expect(screen.getByTestId("uid").textContent).toBe(""), { timeout: 4000 });
    expect(screen.getByTestId("ids").textContent).toBe("");
    expect(deleteChat).not.toHaveBeenCalled();

    // Login A again -> A's durable chats are restored (backend preserved).
    await user.click(screen.getByText("login-a"));
    await waitFor(() => expect(screen.getByTestId("ids").textContent).toBe(`${idA}:chat-1`), { timeout: 4000 });
    // Backend was never mutated on logout across the whole flow.
    expect(deleteChat).not.toHaveBeenCalled();
  });
});
