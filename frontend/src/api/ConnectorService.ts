import type { Connector, ConnectorConnectResult, ConnectorType } from "./types";

/**
 * The single boundary for connector (external memory source) operations.
 * The backend team will provide the real implementation. The Frontend talks
 * ONLY through this interface and never invents OAuth endpoints, connection
 * success, sync counts, or timestamps.
 *
 * PROPOSED contract - requires backend sign-off:
 *   GET    /api/connectors                        -> Connector[]
 *   POST   /api/connectors/{type}/connect         -> ConnectorConnectResult
 *   POST   /api/connectors/{type}/sync            -> Connector
 *   POST   /api/connectors/{type}/pause           -> Connector
 *   DELETE /api/connectors/{type}                 -> { disconnected: boolean }
 */
export interface ConnectorService {
  /** List all connectors and their current backend-reported status. */
  list(): Promise<Connector[]>;
  /** Begin connecting a source; may return an auth URL for a redirect flow. */
  connect(type: ConnectorType): Promise<ConnectorConnectResult>;
  /** Trigger a sync for a connected source. */
  sync(type: ConnectorType): Promise<Connector>;
  /** Pause syncing for a connected source. */
  pauseSync(type: ConnectorType): Promise<Connector>;
  /** Disconnect a source (never deletes data on the external service). */
  disconnect(type: ConnectorType): Promise<{ disconnected: boolean }>;
}

/** The four initial sources, all starting as not connected. */
export const CONNECTOR_TYPES: ConnectorType[] = [
  "whatsapp",
  "telegram",
  "google_drive",
  "google_photos",
];

/** Static presentation metadata (labels/descriptions), not connection state. */
export const CONNECTOR_META: Record<
  ConnectorType,
  { name: string; description: string; brand: string }
> = {
  whatsapp: {
    name: "WhatsApp",
    description: "Search images and visual memories shared through WhatsApp.",
    brand: "#25D366",
  },
  telegram: {
    name: "Telegram",
    description: "Find images, screenshots and documents shared through Telegram.",
    brand: "#2AABEE",
  },
  google_drive: {
    name: "Google Drive",
    description: "Search screenshots, notes, documents and images stored in Drive.",
    brand: "#1FA463",
  },
  google_photos: {
    name: "Google Photos",
    description: "Search your personal photo and screenshot archive.",
    brand: "#4285F4",
  },
};