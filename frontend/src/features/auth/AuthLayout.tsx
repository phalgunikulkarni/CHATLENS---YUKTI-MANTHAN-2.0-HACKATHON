import type { ReactNode } from "react";
import { BrandLogo } from "../../components/BrandLogo";

/** Split-screen auth shell: branding on the left, the form card on the right. */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="auth-shell">
      <aside className="auth-brand">
        <div className="auth-brand-inner">
          <div className="auth-brand-top">
            <BrandLogo size={44} />
            <div>
              <div className="brand-name" style={{ fontSize: 22 }}>ChatLens</div>
              <div className="brand-tag">You remember it. We find it.</div>
            </div>
          </div>
          <div className="auth-brand-copy">
            <h2>Your visual memories in one searchable place.</h2>
            <p>Search screenshots, notes, receipts and documents by describing what you remember.</p>
          </div>
          <div className="auth-brand-foot">Secure sign-in is handled by the ChatLens backend.</div>
        </div>
      </aside>
      <main className="auth-main">
        <div className="auth-card">{children}</div>
      </main>
    </div>
  );
}