import { useCallback, useState } from "react";
import { apiService } from "../api/client";
import type { AnalyzeBillRequest, AnalyzeBillResponse, BillSplit } from "../api/types";
import { useDispatch } from "./index";
import { uid } from "../utils/format";

type Status = "idle" | "loading" | "ready" | "error";

/**
 * Owns Finance/Receipt (Analyze Bill) + Bill-Split state. Delegates entirely to
 * the backend Analyze Bill agent via apiService.analyzeBill (existing OCR
 * context by image id; the backend performs all split math). No bill/split
 * logic in the frontend.
 */
export function useAnalyzeBill() {
  const dispatch = useDispatch();
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<AnalyzeBillResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Split-specific state so the analysis result stays visible while splitting.
  const [splitStatus, setSplitStatus] = useState<Status>("idle");
  const [split, setSplit] = useState<BillSplit | null>(null);
  const [splitError, setSplitError] = useState<string | null>(null);

  const analyze = useCallback(
    async (imageIds: string[]) => {
      if (!imageIds.length) return;
      setStatus("loading"); setErrorMessage(null);
      setSplit(null); setSplitStatus("idle"); setSplitError(null);
      try {
        const res = await apiService.analyzeBill({ imageIds });
        setResult(res);
        if (res.ok && res.fields) {
          setStatus("ready");
          dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Bill analyzed", tone: "success" } });
        } else {
          setStatus("error");
          setErrorMessage(res.notes[0] ?? res.message ?? "The bill could not be analyzed.");
        }
      } catch {
        setStatus("error");
        setErrorMessage("Analyze Bill needs the backend and a receipt image with readable text.");
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Analyze Bill failed", tone: "error" } });
      }
    },
    [dispatch],
  );

  /** Run a split (equal | items) via the backend. `imageIds` re-supplies OCR context. */
  const runSplit = useCallback(
    async (imageIds: string[], opts: Omit<AnalyzeBillRequest, "imageIds" | "operation">) => {
      if (!imageIds.length) return;
      setSplitStatus("loading"); setSplitError(null);
      try {
        const res = await apiService.analyzeBill({ imageIds, operation: "split", ...opts });
        if (res.ok && res.split) {
          setSplit(res.split);
          setSplitStatus("ready");
          dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Bill split", tone: "success" } });
        } else {
          setSplitStatus("error");
          setSplit(null);
          setSplitError(res.notes[0] ?? res.message ?? "The bill could not be split.");
        }
      } catch {
        setSplitStatus("error"); setSplit(null);
        setSplitError("Could not split the bill. Check the inputs and try again.");
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Split failed", tone: "error" } });
      }
    },
    [dispatch],
  );

  const clear = useCallback(() => {
    setResult(null); setStatus("idle"); setErrorMessage(null);
    setSplit(null); setSplitStatus("idle"); setSplitError(null);
  }, []);

  return {
    status, result, errorMessage, analyze,
    splitStatus, split, splitError, runSplit,
    clear,
  };
}
