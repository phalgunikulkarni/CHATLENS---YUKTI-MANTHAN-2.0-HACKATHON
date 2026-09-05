import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StoreProvider } from "../../state/store";
import { FinancePanel } from "./FinancePanel";
import { apiService } from "../../api/client";
import type { AnalyzeBillResponse } from "../../api/types";

const OK: AnalyzeBillResponse = {
  ok: true,
  message: "Bill analyzed.",
  fields: {
    merchant: "Green Leaf Grocery", date: "2024-03-15", total: 8.30,
    currency: "USD", tax: 0.61,
    line_items: [{ name: "Apples", price: 3.5 }, { name: "Milk", price: 2.99 }],
  },
  confidence: 1.0, notes: [],
};

function renderPanel(selectedIds: string[]) {
  return render(
    <StoreProvider>
      <FinancePanel selectedIds={selectedIds} />
    </StoreProvider>,
  );
}

describe("FinancePanel", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("disables the button when nothing is selected", () => {
    renderPanel([]);
    expect(screen.getByRole("button", { name: /select a receipt memory/i })).toBeDisabled();
  });

  it("analyzes the selected memory and renders detected fields + items", async () => {
    const spy = vi.spyOn(apiService, "analyzeBill").mockResolvedValue(OK);
    renderPanel(["img-1"]);
    await userEvent.click(screen.getByRole("button", { name: /analyze selected receipt/i }));
    await waitFor(() => expect(spy).toHaveBeenCalledWith({ imageIds: ["img-1"] }));
    expect(await screen.findByText("Green Leaf Grocery")).toBeInTheDocument();
    expect(screen.getByText("2024-03-15")).toBeInTheDocument();
    expect(screen.getByText("USD 8.30")).toBeInTheDocument();
    expect(screen.getByText("USD 0.61")).toBeInTheDocument();
    expect(screen.getByText("Apples")).toBeInTheDocument();
    expect(screen.getByText("USD 3.50")).toBeInTheDocument();
  });

  it("does not render fields the backend left null (no fabrication)", async () => {
    vi.spyOn(apiService, "analyzeBill").mockResolvedValue({
      ok: true, message: "ok",
      fields: { merchant: null, date: null, total: null, currency: "INR", tax: null, line_items: [] },
      confidence: 0.25, notes: ["total not confidently detected"],
    });
    renderPanel(["img-2"]);
    await userEvent.click(screen.getByRole("button", { name: /analyze selected receipt/i }));
    await waitFor(() => expect(screen.getByText("INR")).toBeInTheDocument());
    // no Merchant/Total/Date rows since they were null
    expect(screen.queryByText("Merchant")).not.toBeInTheDocument();
    expect(screen.queryByText("Total")).not.toBeInTheDocument();
    expect(screen.getByText(/total not confidently detected/i)).toBeInTheDocument();
  });

  it("shows a controlled error state on a failed analysis", async () => {
    vi.spyOn(apiService, "analyzeBill").mockResolvedValue({
      ok: false, message: "No OCR text available for the given input.",
      fields: null, confidence: null, notes: ["No OCR text available for the given input."],
    });
    renderPanel(["img-3"]);
    await userEvent.click(screen.getByRole("button", { name: /analyze selected receipt/i }));
    expect(await screen.findByText(/Couldn’t analyze this bill/i)).toBeInTheDocument();
    expect(screen.getByText(/No OCR text available/i)).toBeInTheDocument();
  });
});
