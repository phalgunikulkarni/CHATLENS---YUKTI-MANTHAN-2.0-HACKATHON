import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StoreProvider } from "../../state/store";
import { FinancePanel } from "./FinancePanel";
import { apiService } from "../../api/client";
import type { AnalyzeBillResponse } from "../../api/types";

const FIELDS = {
  merchant: "Green Leaf Grocery", date: "2024-03-15", total: 8.30, currency: "USD", tax: 0.61,
  line_items: [
    { name: "Apples", price: 3.5 },
    { name: "Milk", price: 2.99 },
    { name: "Bread", price: 1.2 },
  ],
};
const ANALYZE_OK: AnalyzeBillResponse = { ok: true, message: "ok", fields: FIELDS, confidence: 1, notes: [] };

function equalResp(n: number): AnalyzeBillResponse {
  const amt = Math.round((8.3 / n) * 100) / 100;
  return { ...ANALYZE_OK, split: { mode: "equal", currency: "USD", total: 8.3, people_count: n,
    shares: Array.from({ length: n }, (_, i) => ({ person: `Person ${i + 1}`, amount: amt })),
    rounding: { rule: "r", reconciles_to_total: true } } };
}
function itemsResp(): AnalyzeBillResponse {
  return { ...ANALYZE_OK, split: { mode: "items", currency: "USD", total: 8.3, tax: 0.61, tip: 1,
    people: [{ person: "Alice", items_subtotal: 3.5, amount: 4.0 }, { person: "Bob", items_subtotal: 4.19, amount: 4.9 }],
    shared_item_indices: [], rounding: { rule: "r", reconciles_to_total: true } } };
}

async function renderAnalyzed() {
  vi.spyOn(apiService, "analyzeBill").mockResolvedValueOnce(ANALYZE_OK);
  render(<StoreProvider><FinancePanel selectedIds={["img-1"]} /></StoreProvider>);
  await userEvent.click(screen.getByRole("button", { name: /analyze selected receipt/i }));
  await screen.findByText("Green Leaf Grocery");
}

describe("FinancePanel — Bill Split", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("shows the Split Bill section only after analysis with a valid total", async () => {
    await renderAnalyzed();
    expect(screen.getByText("Split Bill")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /split equally/i })).toBeInTheDocument();
  });

  it("equal split sends operation=split/splitMode=equal/people and renders shares", async () => {
    await renderAnalyzed();
    const spy = vi.spyOn(apiService, "analyzeBill").mockResolvedValueOnce(equalResp(2));
    await userEvent.click(screen.getByRole("button", { name: /split equally/i }));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    const arg = spy.mock.calls[0][0];
    expect(arg.operation).toBe("split");
    expect(arg.splitMode).toBe("equal");
    expect(arg.people).toBe(2);
    expect(await screen.findByText("Each person owes")).toBeInTheDocument();
    expect(screen.getAllByText("USD 4.15").length).toBe(2);
  });

  it("equal split includes an optional tip when provided", async () => {
    await renderAnalyzed();
    const spy = vi.spyOn(apiService, "analyzeBill").mockResolvedValueOnce(equalResp(2));
    await userEvent.type(screen.getByLabelText(/Tip \(optional\)/i), "1.50");
    await userEvent.click(screen.getByRole("button", { name: /split equally/i }));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls[0][0].tip).toBe(1.5);
  });

  it("item split sends assignments and renders per-person amounts", async () => {
    await renderAnalyzed();
    await userEvent.click(screen.getByRole("button", { name: /by items/i }));
    // rename people
    const [a, b] = screen.getAllByRole("textbox").filter((el) => (el as HTMLInputElement).value.startsWith("Person"));
    await userEvent.clear(a); await userEvent.type(a, "Alice");
    await userEvent.clear(b); await userEvent.type(b, "Bob");
    // assign all three items
    const selects = screen.getAllByRole("combobox");
    await userEvent.selectOptions(selects[0], "Alice");
    await userEvent.selectOptions(selects[1], "Bob");
    await userEvent.selectOptions(selects[2], "Bob");
    const spy = vi.spyOn(apiService, "analyzeBill").mockResolvedValueOnce(itemsResp());
    await userEvent.click(screen.getByRole("button", { name: /split by items/i }));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    const arg = spy.mock.calls[0][0];
    expect(arg.operation).toBe("split");
    expect(arg.splitMode).toBe("items");
    expect(arg.assignments).toEqual({ Alice: [0], Bob: [1, 2] });
    // result row renders the per-person amount (Alice appears both as input
    // value and result name, so assert on the amount which is unambiguous).
    expect(await screen.findByText("Each person owes")).toBeInTheDocument();
    expect(screen.getByText("USD 4.00")).toBeInTheDocument();
    expect(screen.getByText("USD 4.90")).toBeInTheDocument();
  });

  it("item split validates that every item is assigned", async () => {
    await renderAnalyzed();
    await userEvent.click(screen.getByRole("button", { name: /by items/i }));
    const spy = vi.spyOn(apiService, "analyzeBill");
    // no assignments made
    await userEvent.click(screen.getByRole("button", { name: /split by items/i }));
    expect(await screen.findByText(/Assign every item/i)).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();  // no backend call on invalid input
  });

  it("surfaces a backend-controlled split error", async () => {
    await renderAnalyzed();
    vi.spyOn(apiService, "analyzeBill").mockResolvedValueOnce({
      ok: false, message: "No bill total was confidently detected.",
      fields: FIELDS, confidence: 1, notes: ["No bill total was confidently detected."], split: null,
    });
    await userEvent.click(screen.getByRole("button", { name: /split equally/i }));
    expect(await screen.findByText(/Couldn’t split this bill/i)).toBeInTheDocument();
    expect(screen.getByText(/No bill total/i)).toBeInTheDocument();
  });
});
