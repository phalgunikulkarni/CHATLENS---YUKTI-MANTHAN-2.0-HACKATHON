import type { ReactNode } from "react";
import { BrandLogo } from "../../components/BrandLogo";
import { RippleDistortion } from "../../components/RippleDistortion";

/**
 * Login-only cinematic shell. Owns the full-viewport React Bits RippleDistortion
 * image background and the premium dark layout: branding on the left, glass
 * login card on the right.
 *
 * Isolation: everything is scoped under the `.login-page` root class and this
 * component is rendered ONLY by LoginPage. The ripple mounts/unmounts with this
 * component, so it disappears completely once the user is authenticated and the
 * authenticated app (which never renders this) takes over. AuthLayout (shared
 * with Signup) is intentionally left untouched.
 */
export function LoginLayout({ children }: { children: ReactNode }) {
  return (
    <div className="login-page">
      {/* Full-screen React Bits ripple distorting a local dark cinematic image.
          Sits behind all content; unmounts with LoginPage. */}
      <RippleDistortion
        src="/hero.jpg"
        brushSize={150}
        strength={0.2}
        swirl={1}
        rings={4}
        grayscale
        trigger="both"
        clickStrength={2}
        tint="#160a2e"
        tintAmount={0.28}
        quality="medium"
        enabled={true}
      />
      {/* Readability overlay above the ripple, below content. */}
      <div className="login-overlay" aria-hidden="true" />

      <div className="login-content">
        <section className="login-brand">
          <div className="login-brand-top">
            <BrandLogo size={46} />
            <span className="login-brand-name">ChatLens</span>
          </div>
          <h1 className="login-headline">
            Your visual memories in <span className="login-accent">one searchable place.</span>
          </h1>
          <p className="login-sub">
            Search screenshots, notes, receipts and documents by describing what you remember.
          </p>
          <p className="login-tagline">Same photos. A deeper you.</p>
        </section>

        <section className="login-card-wrap">
          <div className="login-card">{children}</div>
        </section>
      </div>
    </div>
  );
}
