import type { ApiService } from "./ApiService";
import type { ConnectorService } from "./ConnectorService";
import { HttpAdapter } from "./adapters/httpAdapter";
import { NotConnectedAdapter } from "./adapters/notConnectedAdapter";
import { HttpConnectorService } from "./adapters/httpConnectorService";
import { NotConnectedConnectorService } from "./adapters/notConnectedConnectorService";

/**
 * Builds the API_Service and selects an adapter, in priority order:
 *   1. HTTP adapter    - when VITE_API_BASE_URL points at a live backend.
 *   2. NotConnected    - the DEFAULT. Every call rejects so the UI shows an
 *                        honest waiting state and never presents fabricated
 *                        results, scores, or explanations as if they were real.
 *
 * The real retrieval backend is connected later via the HTTP adapter. No other
 * module constructs adapters or issues HTTP directly.
 */
export function createApiService(): ApiService {
  const url = import.meta.env.VITE_API_BASE_URL?.trim();
  if (url) return new HttpAdapter(url);
  return new NotConnectedAdapter();
}

/**
 * Connector (external memory source) service. Uses the HTTP implementation when
 * a backend is configured; otherwise the not-connected service that reports
 * every source as not connected and never fakes a connection.
 */
export function createConnectorService(): ConnectorService {
  const url = import.meta.env.VITE_API_BASE_URL?.trim();
  if (url) return new HttpConnectorService(url);
  return new NotConnectedConnectorService();
}

export const apiService: ApiService = createApiService();
export const connectorService: ConnectorService = createConnectorService();

/** True when a live backend base URL is configured. */
export const IS_BACKEND_CONNECTED = Boolean(import.meta.env.VITE_API_BASE_URL?.trim());

export type { ApiService } from "./ApiService";
export type { ConnectorService } from "./ConnectorService";
