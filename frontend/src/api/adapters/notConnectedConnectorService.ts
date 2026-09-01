import type { ConnectorService } from "../ConnectorService";
import { CONNECTOR_TYPES } from "../ConnectorService";
import { NotConnectedError } from "../errors";
import type { Connector, ConnectorConnectResult, ConnectorType } from "../types";

/**
 * DEFAULT connector service used when no backend is configured. It reports every
 * source as "not_connected" and rejects connect/sync/disconnect with a
 * NotConnectedError, so the UI shows honest "integration coming soon" states and
 * NEVER fakes a connected account, sync count, or timestamp.
 */
export class NotConnectedConnectorService implements ConnectorService {
  async list(): Promise<Connector[]> {
    return CONNECTOR_TYPES.map((type) => ({ type, status: "not_connected" as const }));
  }
  async connect(_type: ConnectorType): Promise<ConnectorConnectResult> {
    throw new NotConnectedError("Connector backend is not connected yet.");
  }
  async sync(_type: ConnectorType): Promise<Connector> {
    throw new NotConnectedError("Connector backend is not connected yet.");
  }
  async pauseSync(_type: ConnectorType): Promise<Connector> {
    throw new NotConnectedError("Connector backend is not connected yet.");
  }
  async disconnect(_type: ConnectorType): Promise<{ disconnected: boolean }> {
    throw new NotConnectedError("Connector backend is not connected yet.");
  }
}