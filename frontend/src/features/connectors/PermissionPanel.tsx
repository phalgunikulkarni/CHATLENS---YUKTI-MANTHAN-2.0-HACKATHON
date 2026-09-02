import { Icon } from "../../components/Icon";

/**
 * Permission explanation shown before connecting. Lists only the access ChatLens
 * would request; it makes no claim that a connection has occurred.
 */
export function PermissionPanel({ name }: { name: string }) {
  return (
    <div className="perm-panel">
      <p className="perm-panel-label">ChatLens requests permission to:</p>
      <ul className="perm-panel-list">
        <li><Icon name="check" size={15} /> Access supported images</li>
        <li><Icon name="check" size={15} /> Read supported media metadata</li>
        <li><Icon name="check" size={15} /> Index visual memories for search</li>
      </ul>
      <div className="perm-panel-note">
        <Icon name="eye" size={15} />
        <span>Your connected sources are used only to make your visual memories searchable. Disconnect {name} anytime.</span>
      </div>
    </div>
  );
}