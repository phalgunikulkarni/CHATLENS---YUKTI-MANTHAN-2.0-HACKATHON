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
    // items render in a table: name cell + amount cell
    expect(screen.getByText("Apples")).toBeInTheDocument();
    expect(screen.getAllByText("USD 3.50").length).toBeGreaterThan(0);

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

  it("split result shows people, total bill, GST/tax included, and per-person amounts (backend values only)", async () => {
    const analyze = {
      ok: true, message: "ok", confidence: 0.9, notes: [],
      fields: { merchant: "Cafe Rio", date: "2024-05-01", total: 12.5, currency: "USD", tax: 1.1, line_items: [] },
    } as AnalyzeBillResponse;
    const split = {
      ok: true, message: "split", confidence: 1, notes: [], fields: analyze.fields,
      split: {
        mode: "equal", currency: "USD", total: 12.5, people_count: 3,
        // deterministic backend split: 12.50 / 3 -> 4.17, 4.17, 4.16 (remainder handled by backend)
        shares: [
          { person: "Person 1", amount: 4.17 },
          { person: "Person 2", amount: 4.17 },
          { person: "Person 3", amount: 4.16 },
        ],
        rounding: { rule: "half-up", sum: 12.5, reconciles_to_total: true, residual_applied_to_last: -0.01 },
      },
    } as AnalyzeBillResponse;

    vi.spyOn(apiService, "analyzeBill").mockResolvedValueOnce(analyze).mockResolvedValueOnce(split);
    const ref = renderExec();
    const u = userEvent.setup();
    await act(async () => { ref.current!.run("analyze_bill"); });
    await waitFor(() => expect(screen.getByText("Cafe Rio")).toBeInTheDocument());

    await u.click(screen.getByRole("button", { name: "Yes" }));
    await u.click(screen.getByRole("button", { name: /Split equally/i }));

    // Summary from backend values only
    await waitFor(() => expect(screen.getByText("People")).toBeInTheDocument());
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Total bill")).toBeInTheDocument();
    expect(screen.getByText("GST/Tax (included)")).toBeInTheDocument();
    // per-person amounts (2 decimals, deterministic; sum reconciles to 12.50)
    expect(screen.getByText("Person 1 — USD 4.17")).toBeInTheDocument();
    expect(screen.getByText("Person 3 — USD 4.16")).toBeInTheDocument();
    const sum = 4.17 + 4.17 + 4.16;
    expect(Math.abs(sum - 12.5) < 0.01).toBe(true);
  });

  it("does NOT offer a split when the total is missing (no split without a total)", async () => {
    vi.spyOn(apiService, "analyzeBill").mockResolvedValue({
      ok: true, message: "ok", confidence: 0.5, notes: [],
      fields: { merchant: "Corner Store", date: null, total: null, currency: "USD", tax: null, line_items: [] },
    } as AnalyzeBillResponse);
    const ref = renderExec();
    await act(async () => { ref.current!.run("analyze_bill"); });
    await waitFor(() => expect(screen.getByText("Corner Store")).toBeInTheDocument());
    // No total -> no split prompt at all
    expect(screen.queryByText("Would you like to split this bill?")).toBeNull();
  });

  it("renders valid fields even when line_items are malformed (no blank page)", async () => {
    const resp = {
      ok: true, message: "ok", confidence: 0.7, notes: [],
      fields: {
        merchant: "Bistro 9", date: "2024-06-01", total: 20, currency: "EUR", tax: 2,
        // malformed: not proper items / missing prices
        line_items: [{ name: "Soup" }, { price: 5 }, null],
      },
    } as unknown as AnalyzeBillResponse;
    vi.spyOn(apiService, "analyzeBill").mockResolvedValue(resp);
    const ref = renderExec();
    await act(async () => { ref.current!.run("analyze_bill"); });
    // valid fields still render; no crash
    await waitFor(() => expect(screen.getByText("Bistro 9")).toBeInTheDocument());
    expect(screen.getByText("EUR 20.00")).toBeInTheDocument();
  });


  it("includes sessionId in the analyze request (prevents the 422 missing-field)", async () => {
    const spy = vi.spyOn(apiService, "analyzeBill").mockResolvedValue({
      ok: true, message: "ok", confidence: 1, notes: [],
      fields: { merchant: "M", date: null, total: 5, currency: "USD", tax: null, line_items: [] },
    } as AnalyzeBillResponse);
    const ref = renderExec(["img-1"]);
    await act(async () => { ref.current!.run("analyze_bill"); });
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ sessionId: expect.any(String), imageIds: ["img-1"] }));
  });

  it("a 422-style error object never crashes React; a readable string is shown and the page stays mounted", async () => {
    // Simulate the adapter having already coerced a 422; but also prove that even
    // if a stray object appeared in notes, rendering does not crash the app.
    vi.spyOn(apiService, "analyzeBill").mockResolvedValue({
      ok: false,
      message: "Could not analyze bill: Field required.",
      fields: null, confidence: null,
      // deliberately hostile: an object with the crashing keys in notes
      notes: [{ type: "missing", loc: ["body", "sessionId"], msg: "Field required", input: {} } as unknown as string],
      split: null,
    } as AnalyzeBillResponse);

    const ref = renderExec([]);
    await act(async () => { ref.current!.run("analyze_bill"); });

    // A readable string error is rendered (from asText coercion), NOT the object.
    await waitFor(() => expect(screen.getByText(/Field required/)).toBeInTheDocument());
    expect(screen.getByText("Failed")).toBeInTheDocument();
    // The workspace is still mounted (no blank page).
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });


  it("renders a full bill workup: header fields, items table (qty/unit), and GST/CGST/SGST summary", async () => {
    const fields = {
      merchant: "Spice Garden", date: "2024-03-05", currency: "INR", total: 880,
      tax: null, invoice_no: "INV-345", time: "20:15", payment_method: "UPI",
      subtotal: 840, discount: 40, taxable_amount: 800, cgst: 20, sgst: 20, igst: null,
      service_charge: 40, other_charges: null, rounding_adjustment: null,
      line_items: [
        { name: "Paneer Tikka", price: 500, qty: 2, unit_price: 250, amount: 500 },
        { name: "Butter Naan", price: 160, qty: 4, unit_price: 40, amount: 160 },
      ],
    };
    vi.spyOn(apiService, "analyzeBill").mockResolvedValue({
      ok: true, message: "ok", confidence: 1, notes: [], fields,
      arithmetic: { line_items_sum: 660, gst_total: 40, computed_total: 880, reconciles: true },
    } as unknown as AnalyzeBillResponse);

    const ref = renderExec();
    await act(async () => { ref.current!.run("analyze_bill"); });
    await waitFor(() => expect(screen.getByText("Spice Garden")).toBeInTheDocument());

    // header fields
    expect(screen.getByText("INV-345")).toBeInTheDocument();
    expect(screen.getByText("UPI")).toBeInTheDocument();
    // items table columns
    expect(screen.getByText("Qty")).toBeInTheDocument();
    expect(screen.getByText("Unit Price")).toBeInTheDocument();
    expect(screen.getByText("Paneer Tikka")).toBeInTheDocument();
    // GST summary — CGST + SGST shown separately, and a GRAND TOTAL row
    expect(screen.getByText("CGST")).toBeInTheDocument();
    expect(screen.getByText("SGST")).toBeInTheDocument();
    expect(screen.getByText("Subtotal")).toBeInTheDocument();
    expect(screen.getByText("Discount")).toBeInTheDocument();
    expect(screen.getByText("Service Charge")).toBeInTheDocument();
    expect(screen.getByText("GRAND TOTAL")).toBeInTheDocument();
    // IGST absent -> not rendered
    expect(screen.queryByText("IGST")).toBeNull();
  });

  it("each Analyze Bill card has an independent Split control/state", async () => {
    const mkFields = (m: string, total: number) => ({
      merchant: m, date: "2024-01-01", currency: "USD", total, tax: null, line_items: [],
    });
    const spy = vi.spyOn(apiService, "analyzeBill");
    // block A analyze, block B analyze, then split A
    spy.mockResolvedValueOnce({ ok: true, message: "ok", confidence: 1, notes: [], fields: mkFields("Bill A", 100) } as AnalyzeBillResponse)
       .mockResolvedValueOnce({ ok: true, message: "ok", confidence: 1, notes: [], fields: mkFields("Bill B", 60) } as AnalyzeBillResponse)
       .mockResolvedValueOnce({ ok: true, message: "split", confidence: 1, notes: [], fields: mkFields("Bill A", 100),
         split: { mode: "equal", currency: "USD", total: 100, people_count: 2,
                  shares: [{ person: "Person 1", amount: 50 }, { person: "Person 2", amount: 50 }],
                  rounding: { rule: "x" } } } as AnalyzeBillResponse);

    const ref = renderExec();
    const u = userEvent.setup();
    await act(async () => { ref.current!.run("analyze_bill"); });
    await waitFor(() => expect(screen.getByText("Bill A")).toBeInTheDocument());
    await act(async () => { ref.current!.run("analyze_bill"); });
    await waitFor(() => expect(screen.getByText("Bill B")).toBeInTheDocument());

    // Two independent split prompts (one per card).
    const prompts = screen.getAllByText("Would you like to split this bill?");
    expect(prompts.length).toBe(2);

    // Split ONLY the first card.
    const yesButtons = screen.getAllByRole("button", { name: "Yes" });
    await u.click(yesButtons[0]);
    const splitButtons = screen.getAllByRole("button", { name: /Split equally/i });
    await u.click(splitButtons[0]);

    // Card A shows per-person shares; Card B still shows its own unaffected prompt.
    await waitFor(() => expect(screen.getByText("Person 1 — USD 50.00")).toBeInTheDocument());
    expect(screen.getByText("Would you like to split this bill?")).toBeInTheDocument(); // B's prompt remains
  });

  it("shows a readable diagnostic (not a wall of not-detected) when nothing could be read", async () => {
    vi.spyOn(apiService, "analyzeBill").mockResolvedValue({
      ok: true, message: "ok", confidence: 0, notes: ["merchant not confidently detected"],
      fields: { merchant: null, date: null, total: null, currency: null, tax: null, line_items: [] },
    } as AnalyzeBillResponse);
    const ref = renderExec();
    await act(async () => { ref.current!.run("analyze_bill"); });
    await waitFor(() => expect(screen.getByText(/Receipt text could not be read/i)).toBeInTheDocument());
  });

});
