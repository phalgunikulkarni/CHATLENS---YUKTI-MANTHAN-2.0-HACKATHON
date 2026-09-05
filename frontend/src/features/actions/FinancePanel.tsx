import { useState } from "react";
import { Icon } from "../../components/Icon";
import { useAnalyzeBill } from "../../hooks/useAnalyzeBill";
import type { BillFields, BillSplit } from "../../api/types";

/**
 * Finance / Receipt panel. Analyzes the currently selected memory/image via the
 * backend Analyze Bill agent (existing OCR context). After a successful analysis
 * WITH a valid total, a compact Bill-Split section appears (Equal | Items). All
 * split math is performed by the backend — the frontend only collects inputs and
 * renders the returned shares. Never fabricates values.
 */
export function FinancePanel({ selectedIds }: { selectedIds: string[] }) {
  const bill = useAnalyzeBill();
  const { status, result, errorMessage, analyze } = bill;
  const disabled = selectedIds.length === 0 || status === "loading";

  return (
    <div className="panel finance-panel">
      <div className="panel-head">
        <Icon name="tag" size={18} style={{ color: "var(--accent)" }} />
        <h3>Analyze Bill</h3>
      </div>
      <div className="panel-body">
        <p className="card-desc" style={{ marginBottom: 10 }}>
          Extract merchant, date, total, tax and items from a selected receipt image.
          Only confidently detected values are shown.
        </p>
        <button
          className="btn btn-primary"
          style={{ width: "100%" }}
          disabled={disabled}
          onClick={() => analyze(selectedIds.slice(0, 1))}
        >
          <Icon name="tag" size={15} />{" "}
          {status === "loading"
            ? "Analyzing…"
            : selectedIds.length === 0
              ? "Select a receipt memory"
              : "Analyze selected receipt"}
        </button>

        {status === "error" && (
          <div className="finance-error" role="alert">
            <strong>Couldn’t analyze this bill.</strong>
            <p className="card-desc">{errorMessage}</p>
          </div>
        )}

        {status === "ready" && result?.fields && (
          <>
            <BillResult fields={result.fields} notes={result.notes} />
            {result.fields.total !== null && (
              <SplitSection bill={bill} imageIds={selectedIds.slice(0, 1)} fields={result.fields} />
            )}
          </>
        )}
      </div>
    </div>
  );
}

function money(value: number | null | undefined, currency: string | null): string | null {
  if (value === null || value === undefined) return null;
  return `${currency ? currency + " " : ""}${value.toFixed(2)}`;
}

function BillResult({ fields, notes }: { fields: BillFields; notes: string[] }) {
  const rows = [
    { label: "Merchant", value: fields.merchant },
    { label: "Date", value: fields.date },
    { label: "Currency", value: fields.currency },
    { label: "Total", value: money(fields.total, fields.currency) },
    { label: "Tax", value: money(fields.tax, fields.currency) },
  ].filter((r) => r.value);

  return (
    <div className="finance-result">
      {rows.length > 0 ? (
        <dl className="finance-fields">
          {rows.map((r) => (
            <div className="finance-row" key={r.label}>
              <dt>{r.label}</dt><dd>{r.value}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="card-desc">No header fields were confidently detected.</p>
      )}
      {fields.line_items.length > 0 && (
        <div className="finance-items">
          <div className="section-title" style={{ marginBottom: 8 }}>Items</div>
          <ul className="finance-item-list">
            {fields.line_items.map((it, i) => (
              <li key={i} className="finance-item">
                <span className="finance-item-name">{it.name}</span>
                <span className="finance-item-price">{money(it.price, fields.currency)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {notes.length > 0 && <p className="finance-notes card-desc">{notes.join(" · ")}</p>}
    </div>
  );
}

type BillHook = ReturnType<typeof useAnalyzeBill>;

function SplitSection({ bill, imageIds, fields }: { bill: BillHook; imageIds: string[]; fields: BillFields }) {
  const { splitStatus, split, splitError, runSplit } = bill;
  const [mode, setMode] = useState<"equal" | "items">("equal");
  const [people, setPeople] = useState(2);
  const [tip, setTip] = useState<string>("");
  const hasItems = fields.line_items.length > 0;

  // Item-split state: itemIndex -> personName ("Shared" is a reserved bucket).
  const [assignedTo, setAssignedTo] = useState<Record<number, string>>({});
  const [nameA, setNameA] = useState("Person 1");
  const [nameB, setNameB] = useState("Person 2");
  const [localError, setLocalError] = useState<string | null>(null);

  const tipNum = () => {
    const t = parseFloat(tip);
    return Number.isFinite(t) && t >= 0 ? t : undefined;
  };

  const submitEqual = () => {
    if (!Number.isInteger(people) || people < 1) return;
    void runSplit(imageIds, { splitMode: "equal", people, tip: tipNum() });
  };

  const submitItems = () => {
    const assignments: Record<string, number[]> = {};
    const shared: number[] = [];
    fields.line_items.forEach((_, i) => {
      const who = assignedTo[i];
      if (who === "Shared") shared.push(i);
      else if (who) (assignments[who] ??= []).push(i);
    });
    // Validation: every item must be assigned (to a person or Shared).
    const assignedCount =
      shared.length + Object.values(assignments).reduce((a, v) => a + v.length, 0);
    if (assignedCount !== fields.line_items.length || Object.keys(assignments).length === 0) {
      // Surface a local validation message through the hook's error channel by
      // calling the backend anyway would be wasteful; show inline instead.
      setLocalError("Assign every item to a person (or mark it Shared), and use at least one person.");
      return;
    }
    setLocalError(null);
    void runSplit(imageIds, { splitMode: "items", assignments, sharedItems: shared, tip: tipNum() });
  };

  const nameOptions = [nameA, nameB, "Shared"];

  return (
    <div className="split-section">
      <div className="section-title" style={{ marginBottom: 8 }}>Split Bill</div>
      <div className="split-mode-tabs">
        <button className={`split-tab ${mode === "equal" ? "active" : ""}`} onClick={() => setMode("equal")}>Equal</button>
        <button
          className={`split-tab ${mode === "items" ? "active" : ""}`}
          onClick={() => setMode("items")}
          disabled={!hasItems}
          title={hasItems ? undefined : "No line items were detected"}
        >
          By items
        </button>
      </div>

      {mode === "equal" ? (
        <div className="split-equal">
          <label className="ct-field">
            <span>Number of people</span>
            <input className="ct-input" type="number" min={1} value={people}
                   onChange={(e) => setPeople(parseInt(e.target.value || "0", 10))} />
          </label>
          <TipInput tip={tip} setTip={setTip} currency={fields.currency} />
          <button className="btn btn-primary" style={{ width: "100%" }}
                  disabled={splitStatus === "loading" || !Number.isInteger(people) || people < 1}
                  onClick={submitEqual}>
            {splitStatus === "loading" ? "Splitting…" : "Split equally"}
          </button>
        </div>
      ) : (
        <div className="split-items">
          <div className="split-people-names">
            <input className="ct-input" value={nameA} onChange={(e) => setNameA(e.target.value)} aria-label="Person A name" />
            <input className="ct-input" value={nameB} onChange={(e) => setNameB(e.target.value)} aria-label="Person B name" />
          </div>
          <ul className="split-item-list">
            {fields.line_items.map((it, i) => (
              <li key={i} className="split-item-row">
                <span className="finance-item-name">{it.name}</span>
                <span className="finance-item-price">{money(it.price, fields.currency)}</span>
                <select className="ct-input split-assign" aria-label={`Assign ${it.name}`}
                        value={assignedTo[i] ?? ""}
                        onChange={(e) => setAssignedTo({ ...assignedTo, [i]: e.target.value })}>
                  <option value="">—</option>
                  {nameOptions.map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </li>
            ))}
          </ul>
          <TipInput tip={tip} setTip={setTip} currency={fields.currency} />
          {localError && <p className="finance-error" role="alert">{localError}</p>}
          <button className="btn btn-primary" style={{ width: "100%" }}
                  disabled={splitStatus === "loading"} onClick={submitItems}>
            {splitStatus === "loading" ? "Splitting…" : "Split by items"}
          </button>
        </div>
      )}

      {splitStatus === "error" && (
        <div className="finance-error" role="alert">
          <strong>Couldn’t split this bill.</strong>
          <p className="card-desc">{splitError}</p>
        </div>
      )}

      {splitStatus === "ready" && split && <SplitResult split={split} />}
    </div>
  );
}

function TipInput({ tip, setTip, currency }: { tip: string; setTip: (v: string) => void; currency: string | null }) {
  return (
    <label className="ct-field">
      <span>Tip (optional){currency ? ` — ${currency}` : ""}</span>
      <input className="ct-input" type="number" min={0} step="0.01" value={tip}
             onChange={(e) => setTip(e.target.value)} placeholder="0.00" />
    </label>
  );
}

function SplitResult({ split }: { split: BillSplit }) {
  const rows = split.mode === "equal"
    ? (split.shares ?? []).map((s) => ({ person: s.person, amount: s.amount, sub: undefined as number | undefined }))
    : (split.people ?? []).map((p) => ({ person: p.person, amount: p.amount, sub: p.items_subtotal }));
  return (
    <div className="split-result">
      <div className="section-title" style={{ margin: "12px 0 8px" }}>Each person owes</div>
      <ul className="split-share-list">
        {rows.map((r, i) => (
          <li key={i} className="split-share-row">
            <span className="split-share-name">{r.person}</span>
            <span className="split-share-amount">{money(r.amount, split.currency)}</span>
          </li>
        ))}
      </ul>
      {split.rounding?.reconciles_to_total === false && (
        <p className="finance-notes card-desc">Shares are rounded to 2 decimals.</p>
      )}
    </div>
  );
}
