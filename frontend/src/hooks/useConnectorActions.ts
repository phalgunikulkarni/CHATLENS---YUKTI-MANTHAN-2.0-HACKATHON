import { useCallback, useEffect } from "react";
import { connectorService } from "../api/client";
import { isNotConnected } from "../api/errors";
import type { Connector, ConnectorType } from "../api/types";
import { useDispatch } from "./useStore";

/**
 * Connector orchestration: the ONLY place the UI talks to the connector service.
 * Loads backend-reported connector state on mount and exposes connect / sync /
 * pause / disconnect. It NEVER fabricates a connected account, count, or
 * timestamp - status changes come only from real service results.
 */
export function useConnectorActions() {
  const dispatch = useDispatch();

  const load = useCallback(async () => {
    dispatch({ type: "CONNECTORS_LOADING" });
    try {
      const items = await connectorService.list();
      dispatch({ type: "CONNECTORS_LOADED", items });
    } catch (err) {
      // A missing backend leaves every connector "not_connected" (never faked).
      if (isNotConnected(err)) dispatch({ type: "CONNECTORS_LOAD_FAILED", message: "" });
      else dispatch({ type: "CONNECTORS_LOAD_FAILED", message: "Could not load connectors." });
    }
  }, [dispatch]);

  useEffect(() => {
    void load();
  }, [load]);

  /** Record a real, backend-confirmed connection (called after the modal
   *  succeeds). Not invoked on failure, so no fake connected state is shown. */
  const markConnected = useCallback(
    (connector: ConnectorType) => {
      const updated: Connector = { type: connector, status: "connected" };
      dispatch({ type: "CONNECTOR_UPDATED", connector: updated });
    },
    [dispatch]
  );

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
        // Best-effort backend call; if it is unavailable we still reset the local
        // state to not_connected (never leaves a stale "connected" badge).
        try {
          await connectorService.disconnect(connector);
        } catch {
          // ignore - fall through to local reset below
        }
        dispatch({ type: "CONNECTOR_UPDATED", connector: { type: connector, status: "not_connected" } });
      }),
    [run, dispatch]
  );

  return { load, markConnected, sync, pauseSync, disconnect };
}