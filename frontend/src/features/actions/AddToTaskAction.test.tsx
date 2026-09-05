import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StoreProvider } from "../../state/store";
import { ActionPanel } from "./ActionPanel";
import { ToastHost } from "../../components/ToastHost";

// Force the agent-backed path and provide a controllable confirmAddTask.
const confirmAddTask = vi.fn();
vi.mock("../../api/agentActions", () => ({
  IS_AGENT_BACKEND: true,
  confirmAddCalendar: vi.fn(),
  confirmAddTask: (...args: unknown[]) => confirmAddTask(...args),
}));

function renderPanel(addTaskTitle?: string, selectedCount = 1) {
  return render(
    <StoreProvider>
      <>
        <ActionPanel
          selectedCount={selectedCount}
          loading={false}
          onSummarize={() => {}}
          onRoadmap={() => {}}
          onExtractKeyPoints={() => {}}
          onRelated={() => {}}
          addToCalendarTitle="Meeting with Rahul"
          addTaskTitle={addTaskTitle}
        />
        <ToastHost />
      </>
    </StoreProvider>,
  );
}

async function openTaskDialog() {
  const area = screen.getByTestId("add-to-task-action");
  await userEvent.click(within(area).getByRole("button", { name: /add task/i }));
  return screen.findByRole("dialog");
}

describe("Add to Task action (in the action area)", () => {
  beforeEach(() => { confirmAddTask.mockReset(); });

  it("renders the Add Task button in the action area, beside Add to Calendar", () => {
    renderPanel("Submit assignment");
    expect(within(screen.getByTestId("add-to-calendar-action")).getByRole("button", { name: /add to calendar/i })).toBeInTheDocument();
    expect(within(screen.getByTestId("add-to-task-action")).getByRole("button", { name: /add task/i })).toBeInTheDocument();
  });

  it("clicking opens the task dialog with the prefilled title", async () => {
    renderPanel("Submit assignment");
    const dialog = await openTaskDialog();
    expect(within(dialog).getByText(/Add task/i)).toBeInTheDocument();
    const titleInput = dialog.querySelector("input.ct-input") as HTMLInputElement;
    expect(titleInput.value).toBe("Submit assignment");
  });

  it("Review requires a title (validation)", async () => {
    renderPanel(undefined); // no prefill -> empty title
    const dialog = await openTaskDialog();
    // due date defaults to today; empty title keeps Review disabled.
    expect(within(dialog).getByRole("button", { name: /review/i })).toBeDisabled();
    const titleInput = dialog.querySelector("input.ct-input") as HTMLInputElement;
    await userEvent.type(titleInput, "Call dentist");
    await waitFor(() =>
      expect(within(dialog).getByRole("button", { name: /review/i })).toBeEnabled(),
    );
  });

  it("confirming submits the expected task request and shows success", async () => {
    confirmAddTask.mockResolvedValue({
      id: "task-1", title: "Submit assignment", due_date: "2026-09-16",
      due_time: null, priority: "medium", completed: false, created_at: 1,
    });
    renderPanel("Submit assignment");
    const dialog = await openTaskDialog();
    await userEvent.click(within(dialog).getByRole("button", { name: /review/i }));
    await userEvent.click(await screen.findByRole("button", { name: /confirm & add/i }));
    await waitFor(() => expect(confirmAddTask).toHaveBeenCalledTimes(1));
    const payload = confirmAddTask.mock.calls[0][0];
    expect(payload.title).toBe("Submit assignment");
    expect(payload.due_date).toBeTruthy();
    expect(payload.priority).toBe("medium");
    expect(await screen.findByText("Task Added")).toBeInTheDocument();
  });

  it("shows a controlled error when task creation fails", async () => {
    confirmAddTask.mockRejectedValue(new Error("backend down"));
    renderPanel("Submit assignment");
    const dialog = await openTaskDialog();
    await userEvent.click(within(dialog).getByRole("button", { name: /review/i }));
    await userEvent.click(await screen.findByRole("button", { name: /confirm & add/i }));
    expect(await screen.findByText("Could not add task")).toBeInTheDocument();
  });
});
