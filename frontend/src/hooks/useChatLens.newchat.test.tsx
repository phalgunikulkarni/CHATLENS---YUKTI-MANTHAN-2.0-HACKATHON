import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { createElement } from "react";

/**
 * Feature: account-scoped-chat-and-isolation (Phase C, task 3.5).
 * Durable New Chat: newConversation() calls createChat() and the store adopts
 * the returned canonical sessionId as BOTH the conversation summary id and the
 * conversation.sessionId. A subsequent search does NOT create a second backend
 * chat (guard against duplicate session creation).
 * Validates: Requirements R3.2, R7.1.
 */

// Mock the API client BEFORE importing modules that read it. vi.hoisted keeps
// the spies available inside the hoisted vi.mock factory without a TDZ error.
const { createChat, listChats, search, renameChat } = vi.hoisted(() => ({
  createChat: vi.fn(),
  listChats: vi.fn(async () => []),
  search: vi.fn(),
  renameChat: vi.fn(async () => ({ sessionId: "x" })),
}));
vi.mock("../api/client", () => ({
  apiService: {
    createChat,
    listChats,
    search,
    renameChat,
    refine: vi.fn(),
  },
}));

import { StoreProvider, rootReducer, initialRootState } from "../state/store";
import { useChatLens } from "./useChatLens";
import { useConversation, useConversations } from "../hooks";

function wrapper({ children }: { children: ReactNode }) {
  return createElement(StoreProvider, null, children);
}

function useHarness() {
  return {
    c: useChatLens(),
    conversation: useConversation(),
    conversations: useConversations(),
  };
}

beforeEach(() => {
  createChat.mockReset();
  search.mockReset();
  renameChat.mockReset();
  renameChat.mockResolvedValue({ sessionId: "x" });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useChatLens durable New Chat", () => {
  it("newConversation adopts the backend canonical sessionId", async () => {
    createChat.mockResolvedValue({ sessionId: "acct-1:sess-42", title: "", createdAt: null, updatedAt: null });
    const { result } = renderHook(useHarness, { wrapper });

    await act(async () => {
      await result.current.c.newConversation();
    });

    expect(createChat).toHaveBeenCalledTimes(1);
    expect(result.current.conversations.activeId).toBe("acct-1:sess-42");
    expect(result.current.conversation.sessionId).toBe("acct-1:sess-42");
    expect(result.current.conversations.summaries[0].id).toBe("acct-1:sess-42");
  });

  it("search after New Chat reuses the canonical id (no duplicate createChat)", async () => {
    createChat.mockResolvedValue({ sessionId: "sess-canon", title: "", createdAt: null, updatedAt: null });
    search.mockResolvedValue({ sessionId: "sess-canon", intent: "search", agentMessage: "ok", results: [] });
    const { result } = renderHook(useHarness, { wrapper });

    await act(async () => {
      await result.current.c.newConversation();
    });
    await act(async () => {
      await result.current.c.runSearch("find osi notes");
    });

    // Exactly one backend chat was created (by New Chat), NOT a second one on search.
    expect(createChat).toHaveBeenCalledTimes(1);
    // The search targeted the canonical session id.
    expect(search).toHaveBeenCalledWith({ query: "find osi notes", sessionId: "sess-canon" });
    expect(result.current.conversation.sessionId).toBe("sess-canon");
  });

  it("first search with no active conversation creates exactly one backend chat", async () => {
    createChat.mockResolvedValue({ sessionId: "sess-first", title: "", createdAt: null, updatedAt: null });
    search.mockResolvedValue({ sessionId: "sess-first", intent: "search", agentMessage: "ok", results: [] });
    const { result } = renderHook(useHarness, { wrapper });

    await act(async () => {
      await result.current.c.runSearch("hello");
    });

    expect(createChat).toHaveBeenCalledTimes(1);
    expect(result.current.conversations.activeId).toBe("sess-first");
    expect(search).toHaveBeenCalledWith({ query: "hello", sessionId: "sess-first" });
  });

  it("CONVERSATION_NEW keys the summary by the canonical id (reducer-level)", () => {
    const next = rootReducer(initialRootState, { type: "CONVERSATION_NEW", id: "canon-1", createdAt: 5 });
    expect(next.conversations.activeId).toBe("canon-1");
    expect(next.conversations.summaries[0].id).toBe("canon-1");
  });
});
