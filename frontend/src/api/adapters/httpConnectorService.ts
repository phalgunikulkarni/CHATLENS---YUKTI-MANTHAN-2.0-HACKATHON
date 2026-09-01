import type { ConnectorService } from "../ConnectorService";
import type { Connector, ConnectorConnectResult, ConnectorType } from "../types";

/**
 * Live connector service targeting the PROPOSED backend contract. Used only when
 * a backend base URL is configured. Thin fetch wrappers; no fabricated data.
 */
export class HttpConnectorService implements ConnectorService {
  constructor(private readonly baseUrl: string) {}

  private async req<T>(path: string, method: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, { method });
    if (!res.ok) throw new Error(`Connector request failed: ${res.status}`);
    return (await res.json()) as T;
  }

  list() {
    return this.req<Connector[]>("/api/connectors", "GET");
  }
  connect(type: ConnectorType) {
    return this.req<ConnectorConnectResult>(`/api/connectors/${type}/connect`, "POST");
  }
  sync(type: ConnectorType) {
    return this.req<Connector>(`/api/connectors/${type}/sync`, "POST");
  }
  pauseSync(type: ConnectorType) {
    return this.req<Connector>(`/api/connectors/${type}/pause`, "POST");
  }
  disconnect(type: ConnectorType) {
    return this.req<{ disconnected: boolean }>(`/api/connectors/${type}`, "DELETE");
  }
}