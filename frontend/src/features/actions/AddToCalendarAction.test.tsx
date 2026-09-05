import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StoreProvider } from "../../state/store";
import { ActionPanel } from "./ActionPanel";
import { ToastHost } from "../../components/ToastHost";

// Force the agent-backed path and provide a controllable confirmAddCalendar.
const confirmAddCalendar = vi.fn();
vi.mock("../../api/agentActions", () => ({
  IS_AGENT_BACKEND: true,
  confirmAddCalendar: (...args: unknown[]) => confirmAddCalendar(...args),
  confirmAddTask: vi.fn(),
}));

function renderPanel(addToCalendarTitle?: string, selectedCount = 1) {
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
          addToCalendarTitle={addToCalendarTitle}
        />
        <ToastHost />
      </>
    </StoreProvider>,
  );
}

async function openDialog() {
  await userEvent.click(screen.getByRole("button", { name: /add to calendar/i }));
  return screen.findByRole("dialog");
}

describe("Add to Calendar action (in the action area)", () => {
  beforeEach(() => { confirmAddCalendar.mockReset(); });

  it("renders the Add to Calendar button in the action area", () => {
    renderPanel("Meeting with Rahul");
    const area = screen.getByTestId("add-to-calendar-action");
    expect(within(area).getByRole("button", { name: /add to calendar/i })).toBeInTheDocument();
  });

  it("clicking opens the event dialog with the prefilled title", async () => {
    renderPanel("Meeting with Rahul");
    const dialog = await openDialog();
    expect(within(dialog).getByText(/Add event/i)).toBeInTheDocument();
    const titleInput = dialog.querySelector("input.ct-input") as HTMLInputElement;
    expect(titleInput.value).toBe("Meeting with Rahul");
  });

  it("Review requires a title (validation)", async () => {
    renderPanel(undefined);  // no prefill -> title empty
    const dialog = await openDialog();
    // date + start time already default; empty title keeps Review disabled.
    expect(within(dialog).getByRole("button", { name: /review/i })).toBeDisabled();
    const titleInput = dialog.querySelector("input.ct-input") as HTMLInputElement;
    await userEvent.type(titleInput, "Dentist");
    await waitFor(() =>
      expect(within(dialog).getByRole("button", { name: /review/i })).toBeEnabled(),
    );
  });

  it("confirming submits the expected calendar event and shows success", async () => {
    confirmAddCalendar.mockResolvedValue({
      id: "evt-1", title: "Meeting with Rahul", date: "2026-09-15", start_time: "16:00",
      end_time: null, timezone: "Asia/Kolkata", participants: "", reminder: null, created_at: 1,
    });
    renderPanel("Meeting with Rahul");
    const dialog = await openDialog();
    fireEvent.change(dialog.querySelector('input[type="date"]') as HTMLInputElement, { target: { value: "2026-09-15" } });
    fireEvent.change(dialog.querySelector('input[type="time"]') as HTMLInputElement, { target: { value: "16:00" } });
    await userEvent.click(within(dialog).getByRole("button", { name: /review/i }));
    await userEvent.click(await screen.findByRole("button", { name: /confirm & add/i }));
    await waitFor(() => expect(confirmAddCalendar).toHaveBeenCalledTimes(1));
    const payload = confirmAddCalendar.mock.calls[0][0];
    expect(payload.title).toBe("Meeting with Rahul");
    expect(payload.date).toBe("2026-09-15");
    expect(payload.start_time).toBe("16:00");
    expect(await screen.findByText("Added to Calendar")).toBeInTheDocument();
  });

  it("shows a controlled error when creation fails", async () => {
    confirmAddCalendar.mockRejectedValue(new Error("backend down"));
    renderPanel("Meeting with Rahul");
    const dialog = await openDialog();
    await userEvent.click(within(dialog).getByRole("button", { name: /review/i }));
    await userEvent.click(await screen.findByRole("button", { name: /confirm & add/i }));
    expect(await screen.findByText("Could not add event")).toBeInTheDocument();
  });
});
