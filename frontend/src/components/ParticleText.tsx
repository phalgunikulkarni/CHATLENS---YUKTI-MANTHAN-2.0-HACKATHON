import { useEffect, useRef } from "react";

type ParticleColor = "white" | "purple" | "split";

interface Props {
  text: string;
  /** Rendered fallback text (kept in DOM for a11y + no-canvas environments). */
  className?: string;
  height?: number;
  /** Particle color: solid white, solid purple, or the legacy top/bottom split. */
  color?: ParticleColor;
  /** Font size as a fraction of width (larger = bigger text). */
  fontScale?: number;
}

/**
 * Dependency-free canvas particle text. Draws `text` to an offscreen canvas,
 * samples opaque pixels into particles, and animates them gently toward their
 * home positions with subtle pointer repulsion. White upper half, purple lower
 * half (matching the ChatLens hero). Degrades gracefully: if canvas/2d is
 * unavailable it simply shows the accessible fallback <span> (aria-label).
 *
 * Frontend-only. No external dependencies.
 */
export function ParticleText({ text, className, height = 120, color = "split", fontScale = 1 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return; // graceful fallback: the <span> below remains visible

    let raf = 0;
    let particles: { x: number; y: number; hx: number; hy: number; vx: number; vy: number; c: string }[] = [];
    const pointer = { x: -9999, y: -9999 };
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const build = () => {
      const w = wrap.clientWidth || 600;
      const h = height;
      canvas.width = w * dpr; canvas.height = h * dpr;
      canvas.style.width = `${w}px`; canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      // Draw the text to sample from. Auto-shrink so the FULL string (incl.
      // punctuation) fits within a horizontal safe padding — never clipped.
      const padX = Math.max(24, w * 0.06);
      const maxTextW = w - padX * 2;
      let fontSize = Math.max(34, Math.min(88, Math.floor((w / 9) * fontScale)));
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "#fff";
      const setFont = (fs: number) => { ctx.font = `900 ${fs}px Inter, system-ui, sans-serif`; };
      setFont(fontSize);
      while (fontSize > 18 && ctx.measureText(text).width > maxTextW) {
        fontSize -= 2; setFont(fontSize);
      }
      ctx.fillText(text, w / 2, h / 2);

      const img = ctx.getImageData(0, 0, w * dpr, h * dpr).data;
      ctx.clearRect(0, 0, w, h);
      particles = [];
      const gap = 4; // sampling density (larger = fewer particles)
      for (let y = 0; y < h; y += gap) {
        for (let x = 0; x < w; x += gap) {
          const idx = (Math.floor(y * dpr) * (w * dpr) + Math.floor(x * dpr)) * 4;
          if (img[idx + 3] > 128) {
            const c =
              color === "white" ? "rgba(255,255,255,0.96)"
              : color === "purple" ? "rgba(160,132,255,0.98)"
              : (y < h * 0.55 ? "rgba(255,255,255,0.95)" : "rgba(150,120,255,0.95)");
            particles.push({
              x: w / 2 + (Math.random() - 0.5) * w, y: h / 2 + (Math.random() - 0.5) * h,
              hx: x, hy: y, vx: 0, vy: 0, c,
            });
          }
        }
      }
    };

    const tick = () => {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      for (const p of particles) {
        // spring home
        p.vx += (p.hx - p.x) * 0.02;
        p.vy += (p.hy - p.y) * 0.02;
        // pointer repulsion
        const dx = p.x - pointer.x, dy = p.y - pointer.y;
        const d2 = dx * dx + dy * dy;
        if (d2 < 1600) {
          const d = Math.max(Math.sqrt(d2), 4);
          p.vx += (dx / d) * 2.2;
          p.vy += (dy / d) * 2.2;
        }
        p.vx *= 0.86; p.vy *= 0.86;
        p.x += p.vx; p.y += p.vy;
        ctx.fillStyle = p.c;
        ctx.fillRect(p.x, p.y, 1.7, 1.7);
      }
      raf = requestAnimationFrame(tick);
    };

    const onMove = (e: PointerEvent) => {
      const r = canvas.getBoundingClientRect();
      pointer.x = e.clientX - r.left; pointer.y = e.clientY - r.top;
    };
    const onLeave = () => { pointer.x = -9999; pointer.y = -9999; };
    const onResize = () => build();

    wrap.classList.add('cl-particle-active');
    build();
    tick();
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerleave", onLeave);
    window.addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(raf);
      wrap.classList.remove('cl-particle-active');
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerleave", onLeave);
      window.removeEventListener("resize", onResize);
    };
  }, [text, height, color, fontScale]);

  return (
    <div ref={wrapRef} className="cl-particle-wrap" aria-label={text}>
      <canvas ref={canvasRef} className="cl-particle-canvas" aria-hidden="true" />
      {/* Accessible + no-canvas fallback (visually hidden when canvas paints). */}
      <span className={`cl-particle-fallback cl-pf-${color} ${className ?? ""}`}>{text}</span>
    </div>
  );
}
