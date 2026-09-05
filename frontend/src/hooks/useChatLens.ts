import { useCallback } from "react";
import type { Dispatch } from "react";
import { apiService } from "../api/client";
import { isNotConnected } from "../api/errors";
import type { ConversationDetail } from "../api/types";
import { useConversation, useConversations, useDispatch, useResults } from "../hooks";
import type { AppAction } from "../state/store";
import { makeTitle } from "../state/conversations.slice";
import type { TurnTranscriptEntry } from "../state/types";
import { uid } from "../utils/format";

const NOT_CONNECTED_MSG =
  "ChatLens backend is not connected yet. Connect the backend to retrieve your memories.";

/**
 * Map a backend-durable ConversationDetail into the in-memory transcript and
 * dispatch a hydration. The backend is the source of truth; we only reconstruct
 * what it actually persisted (role + text). Result grid items are NOT
 * fabricated here — ResultRefs carry only image ids + display metadata (no
 * thumbnails), and per the data-integrity rule we never invent image URLs. The
 * live results grid reflects real retrieval; the transcript reflects history.
 */
function hydrateConversation(dispatch: Dispatch<AppAction>, detail: ConversationDetail): void {
  const messages: TurnTranscriptEntry[] = detail.messages.map((m) => ({
    id: m.id,
    role: m.role === "user" ? "user" : "agent",
    text: m.content,
  }));
  dispatch({
    type: "CONVERSATION_HYDRATED",
    sessionId: detail.sessionId,
    messages,
    activeClues: [],
  });
}

/**
 * Orchestration hook: the ONLY place the UI talks to the API service. It maps
 * user intent to dispatches + apiService calls. When the backend is not
 * connected, calls reject with a NotConnectedError and the UI shows an honest
 * integration state instead of any fabricated data.
 */
export function useChatLens() {
  const dispatch = useDispatch();
  const conversation = useConversation();
  const conversations = useConversations();
  const results = useResults();

  /**
   * New Chat becomes backend-durable. We ask the backend to mint a canonical
   * conversation and adopt its `sessionId` as BOTH the summary id and the
   * session id, so the in-memory snapshot cache is keyed by the canonical id
   * and search/refine target the same backend conversation. When the backend
   * is not connected (or the call fails) we fall back to a local-only id so the
   * mock / not-connected UX still works exactly as before.
   */
  const newConversation = useCallback(async () => {
    dispatch({ type: "VIEW_CHANGED", view: "search" });
    try {
      const summary = await apiService.createChat();
      dispatch({ type: "CONVERSATION_NEW", id: summary.sessionId, createdAt: Date.now() });
      dispatch({ type: "SESSION_STARTED", sessionId: summary.sessionId });
      if (summary.title) {
        dispatch({ type: "CONVERSATION_TITLED", id: summary.sessionId, title: summary.title });
      }
    } catch {
      // NotConnected or transient failure: keep New Chat usable with a local id.
      // The first search will still create/adopt a backend session when possible.
      dispatch({ type: "CONVERSATION_NEW", id: uid("conv"), createdAt: Date.now() });
    }
  }, [dispatch]);

  /**
   * Selecting a conversation hydrates its persisted messages/results from the
   * backend (source of truth). The store swap (CONVERSATION_SELECTED) restores
   * the cached snapshot first; then getChat hydrates the durable transcript so
   * a page refresh / fresh login still shows prior turns. NotConnected falls
   * back to whatever snapshot the cache holds.
   */
  const selectConversation = useCallback(
    async (id: string) => {
      dispatch({ type: "CONVERSATION_SELECTED", id });
      dispatch({ type: "VIEW_CHANGED", view: "search" });
      try {
        const detail = await apiService.getChat(id);
        hydrateConversation(dispatch, detail);
      } catch {
        // NotConnected / missing: keep the cached snapshot; never fabricate.
      }
    },
    [dispatch]
  );

  const runSearch = useCallback(
    async (query: string) => {
      dispatch({ type: "VIEW_CHANGED", view: "search" });

      // Resolve the canonical backend session to target. Guard against creating
      // a new backend chat on every search: only create one when there is NO
      // active conversation yet (explicit New Chat already created its own).
      let sessionId = conversation.sessionId ?? undefined;
      let convId = conversations.activeId ?? undefined;

      if (!convId) {
        // First search with no active conversation: create a durable backend
        // conversation and adopt its canonical id. Falls back to a local id when
        // the backend is not connected so the mock/offline path still works.
        try {
          const summary = await apiService.createChat();
          convId = summary.sessionId;
          sessionId = summary.sessionId;
          dispatch({ type: "CONVERSATION_NEW", id: summary.sessionId, createdAt: Date.now() });
          dispatch({ type: "SESSION_STARTED", sessionId: summary.sessionId });
        } catch {
          convId = uid("conv");
          dispatch({ type: "CONVERSATION_NEW", id: convId, createdAt: Date.now() });
        }
      }

      const activeSummary = conversations.summaries.find((s) => s.id === convId);
      if ((!activeSummary || !activeSummary.title) && convId) {
        dispatch({ type: "CONVERSATION_TITLED", id: convId, title: makeTitle(query) });
        // Persist the title for the owner (best-effort; ignore when not connected).
        if (sessionId) void apiService.renameChat(sessionId, makeTitle(query)).catch(() => {});
      }

      dispatch({ type: "USER_MESSAGE_ADDED", id: uid("u"), text: query });
      dispatch({ type: "TURN_STARTED" });
      dispatch({ type: "SEARCH_STARTED", query });
      try {
        const turn = await apiService.search({ query, sessionId });
        dispatch({ type: "TURN_RECEIVED", id: uid("a"), turn });
        dispatch({ type: "RESULTS_REPLACED", items: turn.results ?? [], query });
        // Adopt the backend-canonical session id (creates one when we had none).
        if (turn.sessionId) dispatch({ type: "SESSION_STARTED", sessionId: turn.sessionId });
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
    [dispatch, conversation.sessionId, conversations.activeId, conversations.summaries]
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

  const summarizeIds = useCallback(async (ids: string[], mode: "summary" | "key_points" = "summary") => {
    if (ids.length === 0) return;
    dispatch({ type: "ACTION_STARTED" });
    try {
      const summary = await apiService.summarize({ sessionId: conversation.sessionId ?? "pending", imageIds: ids, mode });
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
    return summarizeIds(ids, "summary");
  }, [summarizeIds, results.selectedIds, results.items]);

  const extractKeyPoints = useCallback(() => {
    const ids = results.selectedIds.length > 0 ? results.selectedIds : results.items.map((r) => r.id);
    return summarizeIds(ids, "key_points");
  }, [summarizeIds, results.selectedIds, results.items]);

  const relatedMemories = useCallback(async () => {
    const ids = results.selectedIds.length > 0 ? results.selectedIds : results.items.map((r) => r.id);
    if (ids.length === 0) return;
    dispatch({ type: "ACTION_STARTED" });
    try {
      const related = await apiService.relatedMemories({ sessionId: conversation.sessionId ?? "pending", imageId: ids[0] });
      dispatch({ type: "RESULTS_MERGED", items: related });
      dispatch({ type: "ACTIONS_CLEARED" });
      dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: `Found ${related.length} related memories`, tone: related.length ? "success" : "info" } });
    } catch (err) {
      if (isNotConnected(err)) {
        dispatch({ type: "ACTION_NOT_CONNECTED" });
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Related memories need the backend", tone: "error" } });
      } else {
        dispatch({ type: "ACTION_FAILED", message: "Could not find related memories." });
        dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Related memories failed", tone: "error" } });
      }
    }
  }, [dispatch, conversation.sessionId, results.selectedIds, results.items]);

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

  return {
    runSearch, runRefine, removeClue, toggleSelect, openDrawer, closeDrawer,
    newConversation, selectConversation,
    summarize, makeRoadmap, summarizeImage, roadmapImage, extractKeyPoints, relatedMemories,
    proposeSchedule, confirmSchedule, cancelSchedule,
  };
}