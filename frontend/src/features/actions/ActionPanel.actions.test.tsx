import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StoreProvider } from "../../state/store";
import { ActionPanel } from "./ActionPanel";

// Keep the agent-backed buttons self-contained; no network in this test.
vi.mock("../../api/agentActions", () => ({
  IS_AGENT_BACKEND: true,
  confirmAddCalendar: vi.fn(),
  confirmAddTask: vi.fn(),
}));

/**
 * Phase 5 regression: the ActionPanel must expose ALL SIX selected-memory
 * actions together, so the calendar/task actions are discoverable beside the
 * agent actions (the browser-flow "step 3" check).
 */
describe("ActionPanel — all six actions present", () => {
  it("renders Summarize, Revision roadmap, Extract key points, Related memories, Add to Calendar, Add Task", () => {
    render(
      <StoreProvider>
        <ActionPanel
          selectedCount={1}
          loading={false}
          onSummarize={() => {}}
          onRoadmap={() => {}}
          onExtractKeyPoints={() => {}}
          onRelated={() => {}}
          addToCalendarTitle="Some memory"
          addTaskTitle="Some memory"
        />
      </StoreProvider>,
    );
    expect(screen.getByRole("button", { name: /summarize/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /revision roadmap/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /extract key points/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /related memories/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add to calendar/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add task/i })).toBeInTheDocument();
  });
});
