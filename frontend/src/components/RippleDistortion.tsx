import { useEffect, useRef } from "react";
import { Renderer, Program, Mesh, Triangle, Texture, Vec2 } from "ogl";

/**
 * RippleDistortion (React Bits pattern).
 *
 * Loads an IMAGE from `src` into a WebGL texture and distorts it with a liquid
 * ripple that follows the pointer and bursts on click. This mirrors the React
 * Bits RippleDistortion API:
 *
 *   <RippleDistortion src="/hero.jpg" brushSize={150} strength={0.2}
 *                     swirl={1} rings={4} grayscale />
 *
 * The React Bits source is a Pro (paid) component and is not redistributable, so
 * this is a faithful, dependency-light (ogl) implementation of the SAME public
 * API and image-distortion behavior — not a different/custom shader API.
 *
 * Isolation: owns its own <canvas> + pointer listeners; touches no global
 * styles. Rendered only by the pre-login LoginLayout. If WebGL is unavailable
 * (e.g. jsdom in tests) it shows the image via a CSS background fallback and
 * never throws, so the login page keeps working.
 */
export interface RippleDistortionProps {
  /** Image URL to distort (e.g. "/hero.jpg"). */
  src: string;
  brushSize?: number;
  strength?: number;
  swirl?: number;
  rings?: number;
  /** Render the image in grayscale. */
  grayscale?: boolean;
  /** "hover" | "click" | "both" (default "both"). */
  trigger?: "hover" | "click" | "both";
  clickStrength?: number;
  /** Extra dark/purple tint blended over the image. */
  tint?: string;
  tintAmount?: number;
  quality?: "low" | "medium" | "high";
  enabled?: boolean;
  className?: string;
}

function hexToRgb(hex: string): [number, number, number] {
  const m = hex.replace("#", "");
  const v = m.length === 3 ? m.split("").map((c) => c + c).join("") : m;
  const n = parseInt(v, 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

const VERT = `
attribute vec2 position;
attribute vec2 uv;
varying vec2 vUv;
void main() { vUv = uv; gl_Position = vec4(position, 0.0, 1.0); }
`;

const FRAG = `
precision highp float;
varying vec2 vUv;
uniform sampler2D uTex;
uniform vec2 uRes;        // canvas size
uniform vec2 uImg;        // image size (for cover fit)
uniform float uTime;
uniform vec2 uMouse;      // 0..1
uniform float uMouseOn;
uniform vec2 uClick;      // 0..1
uniform float uClickAge;
uniform float uBrush;     // px
uniform float uStrength;
uniform float uSwirl;
uniform float uRings;
uniform float uClickStrength;
uniform float uGray;
uniform vec3 uTint;
uniform float uTintAmount;

// cover-fit the image into the viewport
vec2 coverUv(vec2 uv) {
  float ca = uRes.x / uRes.y;
  float ia = uImg.x / uImg.y;
  vec2 s = ca > ia ? vec2(1.0, ia / ca) : vec2(ca / ia, 1.0);
  return (uv - 0.5) * s + 0.5;
}

// a single expanding ripple's radial displacement magnitude
float rippleMag(vec2 uv, vec2 c, float age, float amp, float brushUv) {
  float dist = distance(uv, c);
  float within = smoothstep(brushUv, 0.0, dist);      // brush falloff
  float wave = sin(dist * (6.2831 * uRings) - age * (3.0 + uSwirl * 2.0));
  float decay = exp(-age * 1.6);
  return wave * within * amp * decay;
}

void main() {
  vec2 uv = vUv;
  float brushUv = uBrush / uRes.y;

  // accumulate radial displacement from pointer + click ripples
  vec2 disp = vec2(0.0);
  if (uMouseOn > 0.5) {
    float m = rippleMag(uv, uMouse, uTime, uStrength, brushUv);
    vec2 dir = normalize(uv - uMouse + 1e-5);
    // swirl: rotate the displacement direction
    float s = uSwirl * m * 3.0;
    dir = mat2(cos(s), -sin(s), sin(s), cos(s)) * dir;
    disp += dir * m;
  }
  {
    float m = rippleMag(uv, uClick, uClickAge, uStrength * uClickStrength, brushUv);
    vec2 dir = normalize(uv - uClick + 1e-5);
    disp += dir * m;
  }

  vec2 iuv = coverUv(uv + disp);
  vec3 col = texture2D(uTex, iuv).rgb;

  if (uGray > 0.5) {
    float g = dot(col, vec3(0.299, 0.587, 0.114));
    col = vec3(g);
  }
  // dark/purple cinematic tint
  col = mix(col, uTint, uTintAmount);

  gl_FragColor = vec4(col, 1.0);
}
`;

export function RippleDistortion({
  src, brushSize = 150, strength = 0.2, swirl = 1, rings = 4, grayscale = false,
  trigger = "both", clickStrength = 2, tint = "#160a2e", tintAmount = 0.28,
  quality = "medium", enabled = true, className,
}: RippleDistortionProps) {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !enabled) return;
    // CSS fallback so the image is visible even before/without WebGL.
    host.style.backgroundImage = `url("${src}")`;
    host.style.backgroundSize = "cover";
    host.style.backgroundPosition = "center";

    let renderer: Renderer;
    try {
      const dprMap = { low: 1, medium: Math.min(window.devicePixelRatio || 1, 1.5), high: Math.min(window.devicePixelRatio || 1, 2) };
      renderer = new Renderer({ dpr: dprMap[quality], alpha: false, antialias: false });
    } catch {
      return; // no WebGL (e.g. jsdom): CSS background fallback remains
    }
    const gl = renderer.gl;
    gl.canvas.className = "ripple-canvas";
    host.appendChild(gl.canvas);

    const texture = new Texture(gl, { generateMipmaps: false });
    const imgEl = new Image();
    imgEl.crossOrigin = "anonymous";
    imgEl.src = src;
    imgEl.onload = () => {
      texture.image = imgEl;
      program.uniforms.uImg.value.set(imgEl.naturalWidth || 1, imgEl.naturalHeight || 1);
    };

    const mouse = new Vec2(0.5, 0.5);
    const click = new Vec2(0.5, 0.5);
    let clickTime = -999;

    const program = new Program(gl, {
      vertex: VERT, fragment: FRAG,
      uniforms: {
        uTex: { value: texture },
        uRes: { value: new Vec2(1, 1) },
        uImg: { value: new Vec2(1600, 1000) },
        uTime: { value: 0 },
        uMouse: { value: mouse },
        uMouseOn: { value: 0 },
        uClick: { value: click },
        uClickAge: { value: 999 },
        uBrush: { value: brushSize },
        uStrength: { value: strength },
        uSwirl: { value: swirl },
        uRings: { value: rings },
        uClickStrength: { value: clickStrength },
        uGray: { value: grayscale ? 1 : 0 },
        uTint: { value: hexToRgb(tint) },
        uTintAmount: { value: tintAmount },
      },
    });
    const mesh = new Mesh(gl, { geometry: new Triangle(gl), program });

    const resize = () => {
      const w = host.clientWidth || window.innerWidth;
      const h = host.clientHeight || window.innerHeight;
      renderer.setSize(w, h);
      program.uniforms.uRes.value.set(gl.drawingBufferWidth, gl.drawingBufferHeight);
    };
    resize();
    window.addEventListener("resize", resize);

    const hoverOn = trigger === "hover" || trigger === "both";
    const clickOn = trigger === "click" || trigger === "both";
    const onMove = (e: PointerEvent) => {
      const r = host.getBoundingClientRect();
      mouse.set((e.clientX - r.left) / r.width, 1 - (e.clientY - r.top) / r.height);
      if (hoverOn) program.uniforms.uMouseOn.value = 1;
    };
    const onLeave = () => { program.uniforms.uMouseOn.value = 0; };
    const onDown = (e: PointerEvent) => {
      if (!clickOn) return;
      const r = host.getBoundingClientRect();
      click.set((e.clientX - r.left) / r.width, 1 - (e.clientY - r.top) / r.height);
      clickTime = performance.now() / 1000;
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerdown", onDown);
    host.addEventListener("pointerleave", onLeave);

    let raf = 0;
    const start = performance.now();
    const loop = () => {
      const now = performance.now();
      program.uniforms.uTime.value = (now - start) / 1000;
      program.uniforms.uClickAge.value = now / 1000 - clickTime;
      renderer.render({ scene: mesh });
      raf = requestAnimationFrame(loop);
    };
    loop();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerdown", onDown);
      host.removeEventListener("pointerleave", onLeave);
      imgEl.onload = null;
      try { gl.canvas.remove(); const ext = gl.getExtension("WEBGL_lose_context"); ext?.loseContext(); } catch { /* noop */ }
    };
  }, [src, brushSize, strength, swirl, rings, grayscale, trigger, clickStrength, tint, tintAmount, quality, enabled]);

  return <div ref={hostRef} className={`ripple-background ${className ?? ""}`} aria-hidden="true" />;
}
