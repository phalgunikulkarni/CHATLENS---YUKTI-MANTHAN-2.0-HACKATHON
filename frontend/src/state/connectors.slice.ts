import type { Connector, ConnectorType } from "../api/types";
import { CONNECTOR_TYPES } from "../api/ConnectorService";

export interface ConnectorsState {
  /** Backend-reported connector state. Defaults to all "not_connected". */
  items: Connector[];
  loading: boolean;
  /** Per-connector in-flight flag (connect/sync/disconnect). */
  busy: Record<string, boolean>;
  error: string | null;
  /** True when connector operations failed because no backend is connected. */
  notConnected: boolean;
}

export const initialConnectorsState: ConnectorsState = {
  items: CONNECTOR_TYPES.map((type) => ({ type, status: "not_connected" })),
  loading: false,
  busy: {},
  error: null,
  notConnected: false,
};

export type ConnectorsAction =
  | { type: "CONNECTORS_LOADING" }
  | { type: "CONNECTORS_LOADED"; items: Connector[] }
  | { type: "CONNECTORS_LOAD_FAILED"; message: string }
  | { type: "CONNECTOR_BUSY"; connector: ConnectorType; busy: boolean }
  | { type: "CONNECTOR_UPDATED"; connector: Connector }
  | { type: "CONNECTOR_NOT_CONNECTED" };

function replace(items: Connector[], updated: Connector): Connector[] {
  return items.map((c) => (c.type === updated.type ? updated : c));
}

export function connectorsReducer(state: ConnectorsState, action: ConnectorsAction): ConnectorsState {
  switch (action.type) {
    case "CONNECTORS_LOADING":
      return { ...state, loading: true, error: null, notConnected: false };
    case "CONNECTORS_LOADED":
      return { ...state, items: action.items, loading: false, error: null };
    case "CONNECTORS_LOAD_FAILED":
      return { ...state, loading: false, error: action.message };
    case "CONNECTOR_BUSY":
      return { ...state, busy: { ...state.busy, [action.connector]: action.busy } };
    case "CONNECTOR_UPDATED":
      return { ...state, items: replace(state.items, action.connector), notConnected: false };
    case "CONNECTOR_NOT_CONNECTED":
      return { ...state, notConnected: true };
    default:
      return state;
  }
}