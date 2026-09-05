import { describe, it, expect, vi, afterEach } from "vitest";
import { createRef } from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StoreProvider } from "../../state/store";
import { apiService } from "../../api/client";
import { ExecutionWorkspace, type ExecHandle } from "./ExecutionWorkspace";
import type { AnalyzeBillResponse } from "../../api/types";

function renderExec(selectedIds = ["img-1"]) {
  const ref = createRef<ExecHandle>();
  render(
    <StoreProvider>
      <ExecutionWorkspace selectedIds={selectedIds} defaultTitle="Receipt" handleRef={ref} />
    </StoreProvider>,
  );
  return ref;
}

afterEach(() => vi.restoreAllMocks());

describe("Analyze Bill execution block", () => {
  it("renders the receipt block WITHOUT crashing when line_items is missing (the blank-page bug)", async () => {
    // Backend legitimately may omit line_items — this used to throw during render
    // (fields.line_items.length) and blank the whole page. Now it must render fine.
    const resp = {
      ok: true, message: "ok", confidence: 0.9, notes: [],
      fields: {
        merchant: "Cafe Rio", date: "2024-05-01", total: 12.5, currency: "USD", tax: 1.1,
        // line_items intentionally omitted / undefined
      },
    } as unknown as AnalyzeBillResponse;
    const spy = vi.spyOn(apiService, "analyzeBill").mockResolvedValue(resp);

    const ref = renderExec();
    await act(async () => { ref.current!.run("analyze_bill"); });

    await waitFor(() => expect(screen.getByText("Cafe Rio")).toBeInTheDocument());
    // Total is shown; no crash; the workspace is still mounted.
    expect(screen.getByText("USD 12.50")).toBeInTheDocument();
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("renders merchant/total/items and offers an equal split that shows per-person amounts", async () => {
    const analyze = {
      ok: true, message: "ok", confidence: 0.9, notes: [],
      fields: {
        merchant: "Green Leaf Grocery", date: "2024-03-15", total: 8.3, currency: "USD", tax: 0.61,
        line_items: [{ name: "Apples", price: 3.5 }, { name: "Milk", price: 2.99 }],
      },
    } as AnalyzeBillResponse;
    const split = {
      ok: true, message: "split", confidence: 1, notes: [], fields: analyze.fields,
      split: {
        mode: "equal", currency: "USD", total: 8.3, people_count: 2,
        shares: [{ person: "Person 1", amount: 4.15 }, { person: "Person 2", amount: 4.15 }],
        rounding: { rule: "half-up" },
      },
    } as AnalyzeBillResponse;

    const spy = vi.spyOn(apiService, "analyzeBill")
      .mockResolvedValueOnce(analyze)  // analyze
      .mockResolvedValueOnce(split);   // split

    const ref = renderExec();
    const u = userEvent.setup();
    await act(async () => { ref.current!.run("analyze_bill"); });

    await waitFor(() => expect(screen.getByText("Green Leaf Grocery")).toBeInTheDocument());
    // the item line renders "Apples — USD 3.50"
    expect(screen.getByText(/Apples — USD 3\.50/)).toBeInTheDocument();

    // split prompt
    expect(screen.getByText("Would you like to split this bill?")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Yes" }));
    await u.click(screen.getByRole("button", { name: /Split equally/i }));

    await waitFor(() => expect(screen.getByText("Person 1 — USD 4.15")).toBeInTheDocument());
    expect(screen.getByText("Person 2 — USD 4.15")).toBeInTheDocument();
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({ operation: "split", splitMode: "equal", people: 2 }),
    );
  });

  it("shows a controlled error (never a blank page) when the API reports failure", async () => {
    vi.spyOn(apiService, "analyzeBill").mockResolvedValue({
      ok: false, message: "No readable total", fields: null, confidence: null, notes: ["No total found"],
    } as AnalyzeBillResponse);

    const ref = renderExec([]);
    await act(async () => { ref.current!.run("analyze_bill"); });

    await waitFor(() => expect(screen.getByText("No total found")).toBeInTheDocument());
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });
});
