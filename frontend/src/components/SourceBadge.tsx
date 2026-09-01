import type { ConnectorMemorySource } from "../api/types";
import { SOURCE_LABEL } from "../utils/format";
import { Icon, type IconName } from "./Icon";

const SOURCE_ICON: Record<ConnectorMemorySource, IconName> = {
  uploaded: "upload",
  whatsapp: "sparkles",
  telegram: "sparkles",
  google_drive: "database",
  google_photos: "image",
};

/** Small indicator showing where a memory came from (backend-provided only). */
export function SourceBadge({ source }: { source: ConnectorMemorySource }) {
  return (
    <span className="source-badge-pill" data-source={source}>
      <Icon name={SOURCE_ICON[source]} size={12} />
      {SOURCE_LABEL[source] ?? source}
    </span>
  );
}