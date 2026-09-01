import { useCallback } from "react";
import { apiService } from "../api/client";
import { isNotConnected } from "../api/errors";
import { useConversation, useDispatch, useResults } from "../hooks";
import { validateFile } from "../state/ingestion.slice";
import type { UploadItem } from "../state/types";
import { uid } from "../utils/format";

const NOT_CONNECTED_MSG =
  "ChatLens backend is not connected yet. Connect the backend to retrieve your memories.";

/**
 * Orchestration hook: the ONLY place the UI talks to the API service. It maps
 * user intent to dispatches + apiService calls. When the backend is not
 * connected, calls reject with a NotConnectedError and the UI shows an honest
 * integration state instead of any fabricated data.
 */
export function useChatLens() {
  const dispatch = useDispatch();
  const conversation = useConversation();
  const results = useResults();

  const runSearch = useCallback(
    async (query: string) => {
      dispatch({ type: "VIEW_CHANGED", view: "search" });
      dispatch({ type: "USER_MESSAGE_ADDED", id: uid("u"), text: query });
      dispatch({ type: "TURN_STARTED" });
      dispatch({ type: "SEARCH_STARTED", query });
      try {
        const turn = await apiService.search({ query, sessionId: conversation.sessionId ?? undefined });
        dispatch({ type: "TURN_RECEIVED", id: uid("a"), turn });
        dispatch({ type: "RESULTS_REPLACED", items: turn.results ?? [], query });
        if (turn.sessionId) dispatch({ type: "SESSION_STARTED", sessionId: turn.sessionId });
        // Record ONLY real, user-performed, backend-answered searches.
        dispatch({
          type: "SEARCH_RECORDED",
          entry: { id: uid("h"), query, at: Date.now(), resultCount: turn.results?.length ?? 0 },
        });
      } catch (err) {
        if (isNotConnected(err)) {
          dispatch({ type: "TURN_NOT_CONNECTED", id: uid("a"), message: NOT_CONNECTED_MSG });
          dispatch({ type: "RETRIEVAL_NOT_CONNECTED" });
        } else {
          dispatch({ type: "TURN_RECEIVED", id: uid("a"), turn: { sessionId: conversation.sessionId ?? "", intent: "search", agentMessage: "Search failed." } });
          dispatch({ type: "RETRIEVAL_FAILED", message: "We could not reach the search service." });
        }
      }
    },
    [dispatch, conversation.sessionId]
  );

  const runRefine = useCallback(
    async (message: string) => {
      const sessionId = conversation.sessionId ?? "pending";
      dispatch({ type: "USER_MESSAGE_ADDED", id: uid("u"), text: message });
      dispatch({ type: "TURN_STARTED" });
      dispatch({ type: "REFINE_STARTED" });
      try {
        const turn = await apiService.refine({ message, sessionId, activeClues: conversation.activeClues });
        dispatch({ type: "TURN_RECEIVED", id: uid("a"), turn });
        if (turn.intent === "search") {
          dispatch({ type: "RESULTS_REPLACED", items: turn.results ?? [], query: message });
        } else if (turn.results) {
          dispatch({ type: "RESULTS_MERGED", items: turn.results });
        } else {
          dispatch({ type: "RESULTS_MERGED", items: results.items });
        }
      } catch (err) {
        if (isNotConnected(err)) {
          dispatch({ type: "TURN_NOT_CONNECTED", id: uid("a"), message: NOT_CONNECTED_MSG });
          dispatch({ type: "RETRIEVAL_NOT_CONNECTED" });
        } else {
          dispatch({ type: "RETRIEVAL_FAILED", message: "We could not refine the search." });
        }
      }
    },
    [dispatch, conversation.sessionId, conversation.activeClues, results.items]
  );

  const removeClue = useCallback(
    async (clueId: string) => {
      dispatch({ type: "CLUE_REMOVED", clueId });
      const remaining = conversation.activeClues.filter((c) => c.id !== clueId);
      dispatch({ type: "REFINE_STARTED" });
      try {
        const turn = await apiService.refine({
          message: results.echoedQuery,
          sessionId: conversation.sessionId ?? "pending",
          activeClues: remaining,
        });
        if (turn.results) dispatch({ type: "RESULTS_MERGED", items: turn.results });
        else dispatch({ type: "RESULTS_MERGED", items: results.items });
      } catch (err) {
        if (isNotConnected(err)) dispatch({ type: "RETRIEVAL_NOT_CONNECTED" });
        else dispatch({ type: "RETRIEVAL_FAILED", message: "We could not update the clues." });
      }
    },
    [dispatch, conversation.activeClues, conversation.sessionId, results.echoedQuery, results.items]
  );

  const toggleSelect = useCallback((id: string) => {
    const willSelect = !results.selectedIds.includes(id);
    dispatch({ type: "RESULT_SELECTION_TOGGLED", id });
    dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: willSelect ? "Memory selected" : "Memory deselected", tone: "info" } });
  }, [dispatch, results.selectedIds]);
  const openDrawer = useCallback((id: string) => dispatch({ type: "DRAWER_OPENED", id }), [dispatch]);
  const closeDrawer = useCallback(() => dispatch({ type: "DRAWER_CLOSED" }), [dispatch]);

  const summarizeIds = useCallback(async (ids: string[]) => {
    if (ids.length === 0) return;
    dispatch({ type: "ACTION_STARTED" });
    try {
      const summary = await apiService.summarize({ sessionId: conversation.sessionId ?? "pending", imageIds: ids });
      dispatch({ type: "SUMMARY_RECEIVED", summary });
      dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Summary ready", tone: "success" } });
    } catch (err) {
      if (isNotConnected(err)) {
        dispatch({ type: "ACTION_NOT_CONNECTED" });
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Summarize needs the backend", tone: "error" } });
      } else {
        dispatch({ type: "ACTION_FAILED", message: "Could not summarize." });
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Summarize failed", tone: "error" } });
      }
    }
  }, [dispatch, conversation.sessionId]);

  const roadmapIds = useCallback(async (ids: string[]) => {
    if (ids.length === 0) return;
    dispatch({ type: "ACTION_STARTED" });
    try {
      const roadmap = await apiService.roadmap({ sessionId: conversation.sessionId ?? "pending", imageIds: ids });
      dispatch({ type: "ROADMAP_RECEIVED", roadmap });
      dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Roadmap ready", tone: "success" } });
    } catch (err) {
      if (isNotConnected(err)) {
        dispatch({ type: "ACTION_NOT_CONNECTED" });
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Roadmap needs the backend", tone: "error" } });
      } else {
        dispatch({ type: "ACTION_FAILED", message: "Could not build roadmap." });
      }
    }
  }, [dispatch, conversation.sessionId]);

  const summarize = useCallback(() => {
    const ids = results.selectedIds.length > 0 ? results.selectedIds : results.items.map((r) => r.id);
    return summarizeIds(ids);
  }, [summarizeIds, results.selectedIds, results.items]);

  const makeRoadmap = useCallback(() => {
    const ids = results.selectedIds.length > 0 ? results.selectedIds : results.items.map((r) => r.id);
    return roadmapIds(ids);
  }, [roadmapIds, results.selectedIds, results.items]);

  const summarizeImage = useCallback((id: string) => summarizeIds([id]), [summarizeIds]);
  const roadmapImage = useCallback((id: string) => roadmapIds([id]), [roadmapIds]);

  const proposeSchedule = useCallback(async (steps: { order: number; title: string; detail?: string }[]) => {
    dispatch({ type: "ACTION_STARTED" });
    try {
      const proposal = await apiService.proposeSchedule({ sessionId: conversation.sessionId ?? "pending", roadmap: steps });
      dispatch({ type: "PROPOSAL_RECEIVED", proposal });
      dispatch({ type: "CONFIRM_DIALOG_OPENED" });
    } catch (err) {
      if (isNotConnected(err)) dispatch({ type: "ACTION_NOT_CONNECTED" });
      else dispatch({ type: "ACTION_FAILED", message: "Could not propose a schedule." });
    }
  }, [dispatch, conversation.sessionId]);

  const confirmSchedule = useCallback(async (events: { title: string; start: string; end?: string; notes?: string }[]) => {
    try {
      await apiService.confirmSchedule({ sessionId: conversation.sessionId ?? "pending", events });
      dispatch({ type: "SCHEDULE_CONFIRMED" });
      dispatch({ type: "CONFIRM_DIALOG_CLOSED" });
      dispatch({ type: "PROPOSAL_CLEARED" });
      dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Events scheduled", tone: "success" } });
    } catch {
      dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Scheduling failed", tone: "error" } });
    }
  }, [dispatch, conversation.sessionId]);

  const cancelSchedule = useCallback(() => {
    dispatch({ type: "CONFIRM_DIALOG_CLOSED" });
    dispatch({ type: "PROPOSAL_CLEARED" });
  }, [dispatch]);

  const clearHistory = useCallback(() => {
    dispatch({ type: "HISTORY_CLEARED" });
    dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Search history cleared", tone: "info" } });
  }, [dispatch]);

  const removeHistoryItem = useCallback((id: string) => {
    dispatch({ type: "HISTORY_ITEM_REMOVED", id });
    dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Search removed", tone: "info" } });
  }, [dispatch]);

  const queueFiles = useCallback((files: File[]) => {
    const items: UploadItem[] = files.map((f) => {
      const validation = validateFile(f.type, f.size);
      return {
        id: uid("up"),
        fileName: f.name,
        fileSize: f.size,
        previewUrl: URL.createObjectURL(f),
        validation,
        status: validation.valid ? "uploaded" : "failed",
        progress: validation.valid ? 100 : 0,
        // Valid files are uploaded client-side but await real backend processing.
        awaitingBackend: validation.valid,
      };
    });
    dispatch({ type: "FILES_QUEUED", items });
  }, [dispatch]);

  const removeUpload = useCallback((id: string) => dispatch({ type: "UPLOAD_ITEM_REMOVED", id }), [dispatch]);

  return {
    runSearch, runRefine, removeClue, toggleSelect, openDrawer, closeDrawer,
    summarize, makeRoadmap, summarizeImage, roadmapImage,
    proposeSchedule, confirmSchedule, cancelSchedule,
    clearHistory, removeHistoryItem, queueFiles, removeUpload,
  };
}