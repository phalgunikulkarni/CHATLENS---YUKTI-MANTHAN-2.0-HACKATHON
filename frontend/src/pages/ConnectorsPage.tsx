import { useState } from "react";
import type { ConnectorType } from "../api/types";
import { useConnectors } from "../hooks";
import { useConnectorActions } from "../hooks/useConnectorActions";
import { ConnectorCard } from "../features/connectors/ConnectorCard";
import { ConnectModal } from "../features/connectors/ConnectModal";
import { ManageConnectorModal } from "../features/connectors/ManageConnectorModal";
import { Icon } from "../components/Icon";

export function ConnectorsPage() {
  const { items, busy } = useConnectors();
  const actions = useConnectorActions();
  const [connecting, setConnecting] = useState<ConnectorType | null>(null);
  const [managing, setManaging] = useState<ConnectorType | null>(null);

  const connectorFor = (type: ConnectorType | null) => items.find((c) => c.type === type);
  const connectTarget = connectorFor(connecting);
  const manageTarget = connectorFor(managing);

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
            onManage={() => setManaging(c.type)}
            onSync={() => actions.sync(c.type)}
          />
        ))}
      </div>

      <section className="privacy-note">
        <div className="privacy-icon"><Icon name="eye" size={18} /></div>
        <div>
          <strong>Your memories, your control.</strong>
          <p>Connect only the sources you want ChatLens to search. Connector permissions are managed by
          the sign-in and backend system, and you can disconnect any source at any time.</p>
        </div>
      </section>

      {connectTarget && (
        <ConnectModal
          connector={connectTarget}
          busy={Boolean(busy[connectTarget.type])}
          onCancel={() => setConnecting(null)}
          onContinue={async () => {
            await actions.connect(connectTarget.type);
            setConnecting(null);
          }}
        />
      )}

      {manageTarget && (
        <ManageConnectorModal
          connector={manageTarget}
          busy={Boolean(busy[manageTarget.type])}
          onSync={() => actions.sync(manageTarget.type)}
          onPause={() => actions.pauseSync(manageTarget.type)}
          onDisconnect={async () => {
            await actions.disconnect(manageTarget.type);
            setManaging(null);
          }}
          onClose={() => setManaging(null)}
        />
      )}
    </div>
  );
}