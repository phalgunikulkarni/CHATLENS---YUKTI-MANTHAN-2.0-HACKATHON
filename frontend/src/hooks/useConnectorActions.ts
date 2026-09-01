import { useCallback, useEffect } from "react";
import { connectorService } from "../api/client";
import { isNotConnected } from "../api/errors";
import type { ConnectorType } from "../api/types";
import { useDispatch } from "./useStore";

/**
 * Connector orchestration: the ONLY place the UI talks to the connector service.
 * Loads backend-reported connector state on mount and exposes connect / sync /
 * pause / disconnect. When no backend is connected, operations dispatch a
 * not-connected flag so the UI shows an honest "integration coming soon" state -
 * it NEVER fabricates a connected account, sync count, or timestamp.
 */
export function useConnectorActions() {
  const dispatch = useDispatch();

  const load = useCallback(async () => {
    dispatch({ type: "CONNECTORS_LOADING" });
    try {
      const items = await connectorService.list();
      dispatch({ type: "CONNECTORS_LOADED", items });
    } catch (err) {
      if (isNotConnected(err)) {
        // Keep the default "not_connected" list; just clear the loading flag.
        dispatch({ type: "CONNECTORS_LOAD_FAILED", message: "" });
      } else {
        dispatch({ type: "CONNECTORS_LOAD_FAILED", message: "Could not load connectors." });
      }
    }
  }, [dispatch]);

  useEffect(() => {
    void load();
  }, [load]);

  const run = useCallback(
    async (connector: ConnectorType, op: () => Promise<void>) => {
      dispatch({ type: "CONNECTOR_BUSY", connector, busy: true });
      try {
        await op();
      } catch (err) {
        if (isNotConnected(err)) dispatch({ type: "CONNECTOR_NOT_CONNECTED" });
        else dispatch({ type: "CONNECTORS_LOAD_FAILED", message: "Connector action failed." });
      } finally {
        dispatch({ type: "CONNECTOR_BUSY", connector, busy: false });
      }
    },
    [dispatch]
  );

  const connect = useCallback(
    (connector: ConnectorType) =>
      run(connector, async () => {
        const result = await connectorService.connect(connector);
        // If the backend returns a redirect-based auth URL, open it.
        if (result.authUrl) window.open(result.authUrl, "_blank", "noopener,noreferrer");
        dispatch({ type: "CONNECTOR_UPDATED", connector: { type: connector, status: result.status } });
      }),
    [run, dispatch]
  );

  const sync = useCallback(
    (connector: ConnectorType) =>
      run(connector, async () => {
        const updated = await connectorService.sync(connector);
        dispatch({ type: "CONNECTOR_UPDATED", connector: updated });
      }),
    [run, dispatch]
  );

  const pauseSync = useCallback(
    (connector: ConnectorType) =>
      run(connector, async () => {
        const updated = await connectorService.pauseSync(connector);
        dispatch({ type: "CONNECTOR_UPDATED", connector: updated });
      }),
    [run, dispatch]
  );

  const disconnect = useCallback(
    (connector: ConnectorType) =>
      run(connector, async () => {
        await connectorService.disconnect(connector);
        dispatch({ type: "CONNECTOR_UPDATED", connector: { type: connector, status: "not_connected" } });
      }),
    [run, dispatch]
  );

  return { load, connect, sync, pauseSync, disconnect };
}