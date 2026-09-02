import type { ApiService } from "./ApiService";
import type { ConnectorService } from "./ConnectorService";
import { HttpAdapter } from "./adapters/httpAdapter";
import { MockAdapter } from "./adapters/mockAdapter";
import { NotConnectedAdapter } from "./adapters/notConnectedAdapter";
import { HttpConnectorService } from "./adapters/httpConnectorService";
import { NotConnectedConnectorService } from "./adapters/notConnectedConnectorService";
import { DemoConnectorService } from "./adapters/demoConnectorService";

/**
 * Builds the API_Service and selects an adapter, in priority order:
 *   1. HTTP adapter    - when VITE_API_BASE_URL points at a live backend.
 *   2. Mock adapter    - ONLY when VITE_USE_MOCK === "true" (explicit dev opt-in).
 *   3. NotConnected    - the DEFAULT. Every call rejects so the UI shows an
 *                        honest "backend not connected" state and never shows
 *                        fabricated data as if it were real.
 *
 * No other module constructs adapters or issues HTTP directly.
 */
export function createApiService(): ApiService {
  const url = import.meta.env.VITE_API_BASE_URL?.trim();
  if (url) return new HttpAdapter(url);
  if (import.meta.env.VITE_USE_MOCK === "true") return new MockAdapter();
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
  // Demo mode (explicit opt-in) exercises the full connect flow without a backend.
  if (import.meta.env.VITE_USE_MOCK === "true") return new DemoConnectorService();
  // Default: no backend -> connectors honestly report not-connected / unable-to-connect.
  return new NotConnectedConnectorService();
}

export const apiService: ApiService = createApiService();
export const connectorService: ConnectorService = createConnectorService();

/** True when a live backend base URL is configured. */
export const IS_BACKEND_CONNECTED = Boolean(import.meta.env.VITE_API_BASE_URL?.trim());

/** True only when explicitly running against the isolated dev/demo mock adapter. */
export const IS_DEMO_MODE = !IS_BACKEND_CONNECTED && import.meta.env.VITE_USE_MOCK === "true";

export type { ApiService } from "./ApiService";
export type { ConnectorService } from "./ConnectorService";