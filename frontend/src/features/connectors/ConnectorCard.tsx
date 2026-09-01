import type { Connector } from "../../api/types";
import { CONNECTOR_META } from "../../api/ConnectorService";
import { Icon } from "../../components/Icon";
import { ConnectorLogo } from "./ConnectorLogo";
import { ConnectorStatusView } from "./ConnectorStatusView";

interface Props {
  connector: Connector;
  busy: boolean;
  onConnect: () => void;
  onManage: () => void;
  onSync: () => void;
}

export function ConnectorCard({ connector, busy, onConnect, onManage, onSync }: Props) {
  const meta = CONNECTOR_META[connector.type];
  const connected = connector.status === "connected";

  return (
    <div className="panel connector-card">
      <div className="connector-head">
        <ConnectorLogo type={connector.type} />
        <div>
          <h3 className="connector-name">{meta.name}</h3>
          <p className="connector-desc">{meta.description}</p>
        </div>
      </div>

      <div className="connector-status-row">
        <ConnectorStatusView connector={connector} />
      </div>

      <div className="connector-actions">
        {connected ? (
          <>
            <button className="btn btn-subtle" onClick={onSync} disabled={busy}>
              <Icon name="history" size={15} /> Sync now
            </button>
            <button className="btn btn-ghost" onClick={onManage} disabled={busy}>
              <Icon name="sparkles" size={15} /> Manage
            </button>
          </>
        ) : (
          <button className="btn btn-primary" onClick={onConnect} disabled={busy || connector.status === "connecting"}>
            <Icon name="arrow" size={15} /> Connect {meta.name}
          </button>
        )}
      </div>
    </div>
  );
}