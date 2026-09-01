import type { RoadmapResponse, ScheduleProposal, SummaryResponse } from "../api/types";
import type { ActionsState } from "./types";

export const initialActionsState: ActionsState = {
  summary: null,
  roadmap: null,
  proposal: null,
  scheduled: false,
  loading: false,
  error: null,
  notConnected: false,
};

export type ActionsAction =
  | { type: "ACTION_STARTED" }
  | { type: "SUMMARY_RECEIVED"; summary: SummaryResponse }
  | { type: "ROADMAP_RECEIVED"; roadmap: RoadmapResponse }
  | { type: "PROPOSAL_RECEIVED"; proposal: ScheduleProposal }
  | { type: "SCHEDULE_CONFIRMED" }
  | { type: "PROPOSAL_CLEARED" }
  | { type: "ACTION_FAILED"; message: string }
  | { type: "ACTION_NOT_CONNECTED" }
  | { type: "ACTIONS_CLEARED" }
  | { type: "SESSION_ENDED" };

export function actionsReducer(state: ActionsState, action: ActionsAction): ActionsState {
  switch (action.type) {
    case "ACTION_STARTED":
      return { ...state, loading: true, error: null, notConnected: false };
    case "SUMMARY_RECEIVED":
      return { ...state, summary: action.summary, loading: false, error: null, notConnected: false };
    case "ROADMAP_RECEIVED":
      return { ...state, roadmap: action.roadmap, loading: false, error: null, notConnected: false };
    case "PROPOSAL_RECEIVED":
      return { ...state, proposal: action.proposal, loading: false, error: null, notConnected: false };
    case "SCHEDULE_CONFIRMED":
      return { ...state, scheduled: true };
    case "PROPOSAL_CLEARED":
      return { ...state, proposal: null };
    case "ACTION_FAILED":
      return { ...state, loading: false, error: action.message, notConnected: false };
    case "ACTION_NOT_CONNECTED":
      return { ...state, loading: false, error: null, notConnected: true };
    case "ACTIONS_CLEARED":
    case "SESSION_ENDED":
      return { ...initialActionsState };
    default:
      return state;
  }
}