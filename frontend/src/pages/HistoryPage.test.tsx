import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import type { ReactNode } from "react";
import { createElement } from "react";

/**
 * Search History page: lists the account's real backend-durable conversations
 * (GET /api/chats), shows an honest empty state when there are none, and opening
 * a conversation restores its transcript via getChat (GET /api/chats/{id}).
 * No fake/sample history is rendered.
 */

const { listChats, getChat, createChat } = vi.hoisted(() => ({
  listChats: vi.fn(),
  getChat: vi.fn(async () => ({ sessionId: "s-1", title: "OSI", messages: [] })),
  createChat: vi.fn(async () => ({ sessionId: "new", title: "", createdAt: null, updatedAt: null })),
}));
vi.mock("../api/client", () => ({
  apiService: { listChats, getChat, createChat, renameChat: vi.fn(), search: vi.fn(), refine: vi.fn() },
}));

import { StoreProvider } from "../state/store";
import { HistoryPage } from "./HistoryPage";

function wrapper({ children }: { children: ReactNode }) {
  return createElement(StoreProvider, null, children);
}

beforeEach(() => {
  listChats.mockReset();
  getChat.mockClear();
});
afterEach(() => vi.clearAllMocks());

describe("HistoryPage (real conversation history)", () => {
  it("lists the account's saved conversations from the backend", async () => {
    listChats.mockResolvedValue([
      { sessionId: "s-2", title: "Python login error", createdAt: "2024-01-02T00:00:00Z" },
      { sessionId: "s-1", title: "CN notes about OSI", createdAt: "2024-01-01T00:00:00Z" },
    ]);
    render(createElement(HistoryPage), { wrapper });
    expect(await screen.findByText("Python login error")).toBeInTheDocument();
    expect(screen.getByText("CN notes about OSI")).toBeInTheDocument();
  });

  it("shows an empty state (no fake history) when there are no conversations", async () => {
    listChats.mockResolvedValue([]);
    render(createElement(HistoryPage), { wrapper });
    expect(await screen.findByText(/no conversations yet/i)).toBeInTheDocument();
  });

  it("opening a conversation restores it via getChat", async () => {
    listChats.mockResolvedValue([{ sessionId: "s-1", title: "CN notes about OSI", createdAt: "2024-01-01T00:00:00Z" }]);
    render(createElement(HistoryPage), { wrapper });
    const item = await screen.findByText("CN notes about OSI");
    fireEvent.click(item);
    await waitFor(() => expect(getChat).toHaveBeenCalledWith("s-1"));
  });

  it("shows an error state with retry when loading fails", async () => {
    listChats.mockRejectedValue(new Error("boom"));
    render(createElement(HistoryPage), { wrapper });
    expect(await screen.findByText(/couldn.t load your history/i)).toBeInTheDocument();
  });
});