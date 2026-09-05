import { useCallback, useState } from "react";
import { apiService } from "../api/client";
import type { ResearchResponse } from "../api/types";
import { useDispatch } from "./index";
import { uid } from "../utils/format";

type Status = "idle" | "loading" | "ready" | "error";

/**
 * Owns Research state + the single research() call. Delegates entirely to the
 * backend Research agent via apiService.research (no research logic in the
 * frontend). Surfaces loading/ready/error + a toast, and keeps the last result.
 */
export function useResearch() {
  const dispatch = useDispatch();
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<ResearchResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const runResearch = useCallback(
    async (query: string) => {
      const q = query.trim();
      if (!q) return;
      setStatus("loading");
      setErrorMessage(null);
      try {
        const res = await apiService.research({ query: q });
        setResult(res);
        if (res.ok) {
          setStatus("ready");
          dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: `Research ready (${res.sources.length} sources)`, tone: "success" } });
        } else {
          // Controlled backend outcome (e.g. no evidence): show it, do not crash.
          setStatus("error");
          setErrorMessage(res.limitations[0] ?? "No reliable evidence was found.");
        }
      } catch {
        setStatus("error");
        setErrorMessage("Research needs the backend and local model. Please try again.");
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Research failed", tone: "error" } });
      }
    },
    [dispatch],
  );

  const clear = useCallback(() => {
    setResult(null); setStatus("idle"); setErrorMessage(null);
  }, []);

  return { status, result, errorMessage, runResearch, clear };
}
