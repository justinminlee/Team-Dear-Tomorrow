import { useEffect, useRef } from "react";
import "./Me2LandingPage.css";

/** Connect this callback to the project's existing login route or modal. */
type Me2LandingPageProps = {
  onLogin: () => void;
};

type Particle = {
  a: number;
  z: number;
  r: number;
  phase: number;
  size: number;
  shade: number;
};

function ParticleRing() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    const count = 2200;
    const rand = (seed: number) => {
      const x = Math.sin(seed * 127.1 + 12.85) * 43758.5453;
      return x - Math.floor(x);
    };
    const points: Particle[] = Array.from({ length: count }, (_, i) => ({
      a: rand(i + 2) * Math.PI * 2,
      z: (rand(i + 40) - 0.5) * 0.35,
      r: 0.76 + (rand(i + 80) - 0.5) * 0.17,
      phase: rand(i + 120) * Math.PI * 2,
      size: 0.38 + rand(i + 160) * 1.03,
      shade: rand(i + 200),
    }));

    let width = 1;
    let height = 1;
    let dpr = 1;
    let time = 0;
    let previous = performance.now();
    let animationFrame = 0;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function resize() {
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      width = Math.max(1, Math.floor(rect.width * dpr));
      height = Math.max(1, Math.floor(rect.height * dpr));
      canvas.width = width;
      canvas.height = height;
      if (reducedMotion) render(performance.now());
    }

    function render(now: number) {
      if (!ctx) return;
      const delta = Math.min(60, now - previous) / 1000;
      previous = now;
      if (!reducedMotion) time += delta;
      ctx.fillStyle = "#111214";
      ctx.fillRect(0, 0, width, height);
      const cx = width * 0.5;
      const cy = height * 0.56;
      const unit = Math.min(width * 0.51, height * 0.58);
      const tilt = 0.97 + Math.sin(time * 0.28) * 0.11;
      const rotation = time * 0.25;
      const ordered: [number, number, number, number, number, number][] = [];

      for (const p of points) {
        const angle = p.a + rotation + p.z * 0.09;
        const radius = p.r * (1 + 0.035 * Math.sin(time * 1.4 + p.phase));
        const x = Math.cos(angle) * radius;
        const z = Math.sin(angle) * radius;
        const y = z * Math.cos(tilt) - p.z * Math.sin(tilt);
        const depth = z * Math.sin(tilt) + p.z * Math.cos(tilt);
        const perspective = 1 / (1 - depth * 0.35);
        const sx = cx + x * unit * perspective;
        const sy = cy + y * unit * 0.76 * perspective;
        if (sx < 0 || sx > width || sy < 0 || sy > height) continue;
        ordered.push([
          depth, sx, sy, p.size * (0.75 + perspective) * dpr,
          p.shade, 0.18 + (0.48 * (depth + 1)) / 2,
        ]);
      }

      ordered.sort((a, b) => a[0] - b[0]);
      ctx.globalCompositeOperation = "lighter";
      for (const p of ordered) {
        const tone = p[4] > 0.9 ? "236,231,221" : p[4] > 0.57 ? "202,197,189" : p[4] > 0.22 ? "170,165,157" : "129,128,127";
        ctx.fillStyle = `rgba(${tone},${Math.min(0.8, p[5])})`;
        ctx.beginPath();
        ctx.arc(p[1], p[2], Math.max(0.35, p[3]), 0, 2 * Math.PI);
        ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
      if (!reducedMotion) animationFrame = requestAnimationFrame(render);
    }

    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();
    if (!reducedMotion) animationFrame = requestAnimationFrame(render);
    return () => {
      cancelAnimationFrame(animationFrame);
      observer.disconnect();
    };
  }, []);

  return (
    <div className="visual" aria-hidden="true">
      <canvas className="me2-particle-canvas" ref={canvasRef} />
    </div>
  );
}

export default function Me2LandingPage({ onLogin }: Me2LandingPageProps) {
  return (
    <main className="me2-landing">
      <header className="site-header">
        <div className="logo">Me²</div>
        <div className="header-note">A CONVERSATION ACROSS TIME</div>
      </header>
      <section className="hero">
        <div className="copy">
          <p className="eyebrow">What if you could talk to tomorrow?</p>
          <h1>Meet your <em>future self.</em></h1>
          <p className="tagline">Not a prediction. A conversation with who you could become.</p>
        </div>
        <ParticleRing />
        <div className="actions">
          <button className="login" type="button" onClick={onLogin}>
            Log in <span aria-hidden="true">↗</span>
          </button>
          <p className="micro">Your future begins with a conversation.</p>
        </div>
      </section>
      <footer className="bottom">
        <span>© Me² AI</span>
        <span>Imagine your future. Hear your possibilities.</span>
      </footer>
    </main>
  );
}
