import { useState } from "react";
import type { ConnectorType } from "../api/types";
import { useConnectors, useDispatch } from "../hooks";
import { useConnectorActions } from "../hooks/useConnectorActions";
import { ConnectorCard } from "../features/connectors/ConnectorCard";
import { ConnectorModal } from "../features/connectors/ConnectorModal";
import { DisconnectConfirmation } from "../features/connectors/DisconnectConfirmation";
import { Icon } from "../components/Icon";
import { uid } from "../utils/format";

export function ConnectorsPage() {
  const { items, busy } = useConnectors();
  const actions = useConnectorActions();
  const dispatch = useDispatch();
  const [connecting, setConnecting] = useState<ConnectorType | null>(null);
  const [disconnecting, setDisconnecting] = useState<ConnectorType | null>(null);

  const connectTarget = items.find((c) => c.type === connecting);

  const openMemories = () => dispatch({ type: "VIEW_CHANGED", view: "library" });

  return (
    <div>
      <header className="connectors-hero">
        <h1>Connect your memories</h1>
        <p>Bring your visual memories together from the places you already use.</p>
      </header>

      <div className="connector-grid">
        {items.map((c) => (
          <ConnectorCard
            key={c.type}
            connector={c}
            busy={Boolean(busy[c.type])}
            onConnect={() => setConnecting(c.type)}
            onOpenMemories={openMemories}
            onDisconnect={() => setDisconnecting(c.type)}
          />
        ))}
      </div>

      <section className="privacy-note">
        <div className="privacy-icon"><Icon name="eye" size={18} /></div>
        <div>
          <strong>Your memories, your control.</strong>
          <p>Your connected sources are used only to make your visual memories searchable. Connector
          permissions are managed by the sign-in and backend system, and you can disconnect any source
          at any time.</p>
        </div>
      </section>

      {connectTarget && (
        <ConnectorModal
          connector={connectTarget}
          onCancel={() => setConnecting(null)}
          onConnected={() => {
            actions.markConnected(connectTarget.type);
            dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Connector connected", tone: "success" } });
            setConnecting(null);
          }}
        />
      )}

      {disconnecting && (
        <DisconnectConfirmation
          type={disconnecting}
          busy={Boolean(busy[disconnecting])}
          onCancel={() => setDisconnecting(null)}
          onConfirm={async () => {
            const type = disconnecting;
            await actions.disconnect(type);
            dispatch({ type: "TOAST_ADDED", toast: { id: uid("t"), message: "Connector disconnected", tone: "info" } });
            setDisconnecting(null);
          }}
        />
      )}
    </div>
  );
}