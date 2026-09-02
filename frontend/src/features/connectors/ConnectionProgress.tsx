import { Icon } from "../../components/Icon";

/** Secure-connection loading state (presentational). */
export function ConnectionProgress({ name }: { name: string }) {
  return (
    <div className="conn-progress" role="status" aria-live="polite">
      <div className="conn-orb"><Icon name="sparkles" size={22} /></div>
      <div className="conn-progress-title">Connecting to {name}...</div>
      <div className="conn-progress-sub">Securely establishing connection...</div>
    </div>
  );
}