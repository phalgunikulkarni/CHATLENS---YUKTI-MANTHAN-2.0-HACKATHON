import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "../../components/Icon";
import { apiService } from "../../api/client";
import { useResearch } from "../../hooks/useResearch";
import { useAnalyzeBill } from "../../hooks/useAnalyzeBill";
import { AddEventModal } from "../calendar/AddEventModal";
import { AddTaskModal } from "../tasks/AddTaskModal";
import { todayISO } from "../calendar/calendarUtils";
import { confirmAddCalendar, confirmAddTask, IS_AGENT_BACKEND } from "../../api/agentActions";
import { calendarTasksService } from "../../api/calendarTasksClient";
import { useDispatch } from "../../hooks";
import { uid } from "../../utils/format";
import type { ActionId } from "./ActionGrid";
import { ACTIONS } from "./ActionGrid";
import type {
  AnalyzeBillResponse, BillFields, BillLineItem, BillSplit, ResearchResponse, SearchResult, SummaryResponse,
} from "../../api/types";

type BlockStatus = "running" | "done" | "error";
interface Block {
  key: string;
  action: ActionId;
  title: string;
  status: BlockStatus;
  error?: string;
  summary?: SummaryResponse;
  research?: ResearchResponse;
  bill?: AnalyzeBillResponse;
  related?: SearchResult[];
  splitting?: boolean;
  splitError?: string;
}

const labelOf = (id: ActionId) => ACTIONS.find((a) => a.id === id)?.label ?? id;

export interface ExecHandle {
  run: (id: ActionId) => void;
}

/**
 * Central, append-only execution workspace. Each clicked action creates a block
 * that runs the EXISTING frontend handler/API and renders its real result.
 * Previous blocks remain visible; new blocks append below. Calendar/Task open
 * the existing confirmation modals and append a block on success.
 */
export function ExecutionWorkspace({
  selectedIds, defaultTitle, sessionId, handleRef,
}: {
  selectedIds: string[];
  defaultTitle?: string;
  sessionId?: string | null;
  handleRef: React.MutableRefObject<ExecHandle | null>;
}) {
  const dispatch = useDispatch();
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [calOpen, setCalOpen] = useState(false);
  const [taskOpen, setTaskOpen] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const research = useResearch();
  const bill = useAnalyzeBill();
  const [researchQuery, setResearchQuery] = useState("");

  const patch = useCallback((key: string, p: Partial<Block>) => {
    setBlocks((prev) => prev.map((b) => (b.key === key ? { ...b, ...p } : b)));
  }, []);

  const append = useCallback((action: ActionId): string => {
    const key = uid("blk");
    setBlocks((prev) => [...prev, { key, action, title: labelOf(action), status: "running" }]);
    return key;
  }, []);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [blocks.length]);

  const runSummarizeLike = useCallback(async (action: ActionId, mode: "summary" | "key_points" | "roadmap") => {
    const ids = selectedIds;
    const key = append(action);
    try {
      if (mode === "roadmap") {
        // roadmap uses the dedicated endpoint but we render via summary shape
        const r = await apiService.roadmap({ sessionId: sessionId ?? "pending", imageIds: ids });
        const summary: SummaryResponse = {
          sessionId: r.sessionId, summary: "", usedImageIds: ids,
          points: r.steps.map((s) => `${s.order}. ${s.title}${s.detail ? " — " + s.detail : ""}`),
        };
        patch(key, { status: "done", summary });
      } else {
        const r = await apiService.summarize({ sessionId: sessionId ?? "pending", imageIds: ids, mode });
        const hasContent = Boolean((r.summary && r.summary.trim()) || (r.points && r.points.length));
        patch(key, hasContent ? { status: "done", summary: r }
                              : { status: "error", error: r.summary || "No text could be extracted from the selected memory." });
      }
    } catch {
      patch(key, { status: "error", error: "This action needs the backend and readable memory text." });
    }
  }, [append, patch, selectedIds, sessionId]);

  const runRelated = useCallback(async () => {
    const key = append("related");
    try {
      const first = selectedIds[0];
      const items = await apiService.relatedMemories({ sessionId: sessionId ?? "pending", imageId: first ?? "" });
      patch(key, { status: "done", related: items });
    } catch {
      patch(key, { status: "error", error: "Could not find related memories." });
    }
  }, [append, patch, selectedIds, sessionId]);

  const runResearchBlock = useCallback(async (query: string) => {
    const q = query.trim(); if (!q) return;
    const key = append("research");
    try {
      const r = await apiService.research({ query: q });
      patch(key, r.ok ? { status: "done", research: r, title: `Research · ${q}` }
                       : { status: "error", error: r.limitations[0] ?? "No reliable evidence found." });
    } catch {
      patch(key, { status: "error", error: "Research needs the backend and local model." });
    }
  }, [append, patch]);

  const runBill = useCallback(async () => {
    const key = append("analyze_bill");
    try {
      const r = await apiService.analyzeBill({ imageIds: selectedIds.slice(0, 1) });
      patch(key, r.ok && r.fields ? { status: "done", bill: r }
                                  : { status: "error", error: r.notes?.[0] ?? r.message ?? "Could not analyze this bill." });
    } catch {
      patch(key, { status: "error", error: "Analyze Bill needs a receipt image with readable text." });
    }
  }, [append, patch, selectedIds]);

  // Equal split of an existing analyzed bill block, using the EXISTING split API.
  // Updates the block's bill.split in place (append-only: same block, no new route).
  const runSplit = useCallback(async (key: string, people: number) => {
    setBlocks((prev) => prev.map((b) => (b.key === key ? { ...b, splitting: true, splitError: undefined } : b)));
    try {
      const r = await apiService.analyzeBill({
        imageIds: selectedIds.slice(0, 1), operation: "split", splitMode: "equal", people,
      });
      if (r.ok && r.split) {
        setBlocks((prev) => prev.map((b) =>
          b.key === key && b.bill ? { ...b, splitting: false, bill: { ...b.bill, split: r.split } } : b));
      } else {
        setBlocks((prev) => prev.map((b) =>
          b.key === key ? { ...b, splitting: false, splitError: r.notes?.[0] ?? r.message ?? "Could not split this bill." } : b));
      }
    } catch {
      setBlocks((prev) => prev.map((b) =>
        b.key === key ? { ...b, splitting: false, splitError: "Splitting needs the backend and a valid total." } : b));
    }
  }, [selectedIds]);

  // expose run() to the parent action grid
  useEffect(() => {
    handleRef.current = {
      run: (id: ActionId) => {
        switch (id) {
          case "summarize": return void runSummarizeLike("summarize", "summary");
          case "key_points": return void runSummarizeLike("key_points", "key_points");
          case "roadmap": return void runSummarizeLike("roadmap", "roadmap");
          case "related": return void runRelated();
          case "research": setResearchQuery(""); return void runResearchBlock(defaultTitle || "");
          case "analyze_bill": return void runBill();
          case "add_calendar": return setCalOpen(true);
          case "add_task": return setTaskOpen(true);
        }
      },
    };
  }, [handleRef, runSummarizeLike, runRelated, runResearchBlock, runBill, defaultTitle]);

  return (
    <div className="cl-exec">
      {blocks.length === 0 && (
        <div className="cl-exec-empty">
          <div className="cl-exec-empty-icon"><Icon name="sparkles" size={26} /></div>
          <p>Pick an action above. Results appear here — one card per action, newest at the bottom.</p>
        </div>
      )}

      {blocks.map((b) => (
        <ExecBlock key={b.key} block={b} onResearchRerun={runResearchBlock}
                   researchQuery={researchQuery} setResearchQuery={setResearchQuery}
                   onSplit={runSplit} />
      ))}
      <div ref={endRef} />

      {calOpen && (
        <AddEventModal
          defaultDate={todayISO()} defaultTitle={defaultTitle}
          onCancel={() => setCalOpen(false)}
          onCreate={async (input) => {
            const key = append("add_calendar");
            try {
              if (IS_AGENT_BACKEND) await confirmAddCalendar(input);
              else await calendarTasksService.createCalendarEvent(input);
              patch(key, { status: "done", title: `Added to Calendar · ${input.title}` });
              dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Added to Calendar", tone: "success" } });
            } catch {
              patch(key, { status: "error", error: "Could not add the event." });
            }
          }}
        />
      )}
      {taskOpen && (
        <AddTaskModal
          defaultTitle={defaultTitle}
          onCancel={() => setTaskOpen(false)}
          onCreate={async (input) => {
            const key = append("add_task");
            try {
              if (IS_AGENT_BACKEND) await confirmAddTask(input);
              else await calendarTasksService.createTask(input);
              patch(key, { status: "done", title: `Task Added · ${input.title}` });
              dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Task Added", tone: "success" } });
            } catch {
              patch(key, { status: "error", error: "Could not add the task." });
            }
          }}
        />
      )}
      {/* keep hooks referenced so linters see them wired for future inline use */}
      <span style={{ display: "none" }}>{research.status}{bill.status}</span>
    </div>
  );
}

function money(v: number | null | undefined, currency: string | null): string | null {
  if (v === null || v === undefined) return null;
  return `${currency ? currency + " " : ""}${v.toFixed(2)}`;
}

function ExecBlock({ block, onSplit }: {
  block: Block;
  onResearchRerun: (q: string) => void;
  researchQuery: string;
  setResearchQuery: (v: string) => void;
  onSplit: (key: string, people: number) => void;
}) {
  const icon = ACTIONS.find((a) => a.id === block.action)?.icon ?? "sparkles";
  return (
    <div className={`cl-block ${block.status}`}>
      <div className="cl-block-head">
        <span className="cl-block-icon"><Icon name={icon} size={16} /></span>
        <span className="cl-block-title">{block.title}</span>
        <span className={`cl-block-status ${block.status}`}>
          {block.status === "running" ? "Running…" : block.status === "error" ? "Failed" : "Done"}
        </span>
      </div>

      {block.status === "running" && (
        <div className="cl-block-body"><div className="cl-ripple" aria-hidden="true" />
          <p className="cl-muted">Working in your local ChatLens workspace…</p></div>
      )}
      {block.status === "error" && (
        <div className="cl-block-body"><p className="cl-error">{block.error}</p></div>
      )}

      {block.status === "done" && block.summary && (
        <div className="cl-block-body">
          {block.summary.summary && <p className="cl-text">{block.summary.summary}</p>}
          {block.summary.points && block.summary.points.length > 0 && (
            <ul className="cl-points">{block.summary.points.map((p, i) => <li key={i}>{p}</li>)}</ul>
          )}
        </div>
      )}

      {block.status === "done" && block.related && (
        <div className="cl-block-body">
          {block.related.length === 0 ? <p className="cl-muted">No related memories found.</p> : (
            <div className="cl-related">{block.related.map((r) => (
              <a key={r.id} className="cl-related-card" href={r.fullUrl || r.thumbnailUrl} target="_blank" rel="noopener noreferrer">
                <img src={r.thumbnailUrl} alt={r.title ?? "memory"} />
                <span>{r.title ?? r.category ?? "Memory"}</span>
              </a>
            ))}</div>
          )}
        </div>
      )}

      {block.status === "done" && block.research && (
        <div className="cl-block-body">
          <p className="cl-text">{block.research.research_answer}</p>
          {block.research.key_findings.length > 0 && (
            <ul className="cl-points">{block.research.key_findings.map((k, i) => <li key={i}>{k}</li>)}</ul>
          )}
          <div className="cl-sources">
            {block.research.sources.map((s, i) => (
              <div key={i} className="cl-source">
                <div className="cl-source-title">{s.title ?? "(untitled)"}</div>
                <div className="cl-source-meta">
                  {s.provider && <span className="cl-badge">{s.provider}</span>}
                  {(s.year || s.publication_date) && <span>{s.publication_date ?? s.year}</span>}
                  {s.doi && <span>DOI: {s.doi}</span>}
                </div>
                {s.url && <a className="cl-link" href={s.url} target="_blank" rel="noopener noreferrer">Open source</a>}
              </div>
            ))}
          </div>
          {block.research.limitations.length > 0 && (
            <p className="cl-muted">{block.research.limitations.join(" · ")}</p>
          )}
        </div>
      )}

      {block.status === "done" && block.bill && block.bill.fields && (
        <BillBody
          fields={block.bill.fields}
          split={block.bill.split ?? null}
          notes={block.bill.notes ?? []}
          splitting={Boolean(block.splitting)}
          splitError={block.splitError}
          onSplit={(people) => onSplit(block.key, people)}
        />
      )}
    </div>
  );
}

function BillBody({ fields, split, notes, splitting, splitError, onSplit }: {
  fields: BillFields;
  split: BillSplit | null;
  notes: string[];
  splitting: boolean;
  splitError?: string;
  onSplit: (people: number) => void;
}) {
  // "want" tracks the split prompt: null = not asked yet, false = declined, true = entering people.
  const [want, setWant] = useState<null | boolean>(null);
  const [people, setPeople] = useState(2);

  // Defensive: backend may omit line_items / non-numeric prices. Never crash the render.
  const items = Array.isArray(fields.line_items) ? fields.line_items : [];
  const safeNotes = Array.isArray(notes) ? notes : [];

  const rows = [
    { label: "Merchant", value: fields.merchant },
    { label: "Date", value: fields.date },
    { label: "Currency", value: fields.currency },
    { label: "Total", value: money(fields.total, fields.currency) },
    { label: "Tax", value: money(fields.tax, fields.currency) },
  ].filter((r) => r.value);

  // Evidence-only explanation: built strictly from extracted values (never invented).
  const analysis = billAnalysis(fields, items);
  const equalShares = split && split.mode === "equal" ? (split.shares ?? []) : [];

  return (
    <div className="cl-block-body">
      <dl className="cl-fields">{rows.map((r) => (
        <div className="cl-field-row" key={r.label}><dt>{r.label}</dt><dd>{r.value}</dd></div>
      ))}</dl>

      {items.length > 0 && (
        <ul className="cl-points">{items.map((it, i) => {
          const priced = typeof it?.price === "number" ? money(it.price, fields.currency) : null;
          return <li key={i}>{it?.name ?? "Item"}{priced ? ` — ${priced}` : ""}</li>;
        })}</ul>
      )}

      {analysis && <p className="cl-text">{analysis}</p>}
      {safeNotes.length > 0 && <p className="cl-muted">{safeNotes.join(" · ")}</p>}

      {/* Split prompt — inline, append-only. Only offered when a numeric total exists. */}
      {typeof fields.total === "number" && (
        <div className="cl-split">
          {equalShares.length > 0 ? (
            <div className="cl-split-result">
              <p className="cl-text">Equal split{split?.people_count ? ` · ${split.people_count} people` : ""}:</p>
              <ul className="cl-points">{equalShares.map((sh, i) => (
                <li key={i}>{sh.person} — {money(sh.amount, split?.currency ?? fields.currency)}</li>
              ))}</ul>
            </div>
          ) : want === null ? (
            <div className="cl-split-ask">
              <span className="cl-text">Would you like to split this bill?</span>
              <div className="cl-split-actions">
                <button type="button" className="cl-action" onClick={() => setWant(false)}>No</button>
                <button type="button" className="cl-action" onClick={() => setWant(true)}>Yes</button>
              </div>
            </div>
          ) : want === false ? (
            <p className="cl-muted">Bill analysis complete.</p>
          ) : (
            <div className="cl-split-ask">
              <label className="cl-text" htmlFor="cl-split-people">How many people?</label>
              <div className="cl-split-actions">
                <input
                  id="cl-split-people" className="cl-input" type="number" min={1} max={100} value={people}
                  onChange={(e) => setPeople(Math.max(1, Math.min(100, Number(e.target.value) || 1)))}
                  style={{ width: 80 }}
                />
                <button type="button" className="cl-action" disabled={splitting}
                        onClick={() => onSplit(people)}>
                  {splitting ? "Splitting…" : "Split equally"}
                </button>
              </div>
              {splitError && <p className="cl-error">{splitError}</p>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Build a short, evidence-only sentence about the expense. Uses ONLY extracted
// values; if nothing concrete is known it returns null (never invents a purpose).
function billAnalysis(fields: BillFields, items: BillLineItem[]): string | null {
  const parts: string[] = [];
  if (fields.merchant) parts.push(`Purchase at ${fields.merchant}`);
  else if (items.length > 0) parts.push("Purchase");
  else return null;
  if (fields.date) parts.push(`on ${fields.date}`);
  if (typeof fields.total === "number") parts.push(`totalling ${money(fields.total, fields.currency)}`);
  const named = items.map((it) => it?.name).filter((n): n is string => Boolean(n));
  if (named.length > 0) {
    const preview = named.slice(0, 3).join(", ");
    parts.push(`covering ${preview}${named.length > 3 ? ` and ${named.length - 3} more item(s)` : ""}`);
  }
  return parts.join(" ") + ".";
}
