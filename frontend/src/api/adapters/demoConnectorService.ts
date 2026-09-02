import type { ConnectorService } from "../ConnectorService";
import { CONNECTOR_TYPES } from "../ConnectorService";
import type { Connector, ConnectorConnectResult, ConnectorType } from "../types";

/**
 * DEMO connector service - used ONLY when VITE_USE_MOCK === "true" (explicit dev
 * opt-in), so the full connection flow (connecting -> connected -> disconnect)
 * can be demonstrated without a backend. It is clearly labeled demo behavior and
 * is never used in the default build, where connectors honestly report
 * not-connected / unable-to-connect instead of faking success.
 */
export class DemoConnectorService implements ConnectorService {
  private connected = new Set<ConnectorType>();

  async list(): Promise<Connector[]> {
    return CONNECTOR_TYPES.map((type) => ({
      type,
      status: this.connected.has(type) ? ("connected" as const) : ("not_connected" as const),
    }));
  }

  async connect(type: ConnectorType): Promise<ConnectorConnectResult> {
    await new Promise((r) => setTimeout(r, 900));
    this.connected.add(type);
    return { type, status: "connected" };
  }

  async sync(type: ConnectorType): Promise<Connector> {
    await new Promise((r) => setTimeout(r, 500));
    return { type, status: "connected", syncStatus: "synced" };
  }

  async pauseSync(type: ConnectorType): Promise<Connector> {
    return { type, status: "connected", syncStatus: "paused" };
  }

  async disconnect(type: ConnectorType): Promise<{ disconnected: boolean }> {
    await new Promise((r) => setTimeout(r, 400));
    this.connected.delete(type);
    return { disconnected: true };
  }
}