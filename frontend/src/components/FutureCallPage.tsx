import { useEffect, useRef, useState } from "react";
import "./FutureCallPage.css";

/**
 * Visual-only, real-call-ready component. No demo audio, mic recorder, or audio upload.
 * The calling app owns the AI audio playback, microphone and call session.
 * Pass a normalized (0...1) level from the ACTUAL AI output audio stream.
 */
export interface FutureCallPageProps {
  /** AI speech/output loudness, normalized to 0..1. Set 0 while silent. */
  aiAudioLevel?: number;
  /** The call is active once the backend confirms it. */
  connected?: boolean;
  /** Whether the user's microphone is currently muted. Parent owns real mute state. */
  muted?: boolean;
  /** Handle real microphone mute/unmute in the parent. */
  onToggleMute?: () => void;
  /** Terminate the actual AI call/session in the parent. */
  onEndCall?: () => void | Promise<void>;
  /** Optional caption supplied by AI speech-to-text. */
  caption?: string;
}

type Particle = { a: number; z: number; r: number; phase: number; size: number; shade: number };
const TOTAL_PARTICLES = 2200;
const random = (n: number) => { const v = Math.sin(n * 127.1 + 12.85) * 43758.5453; return v - Math.floor(v); };
const particles: Particle[] = Array.from({ length: TOTAL_PARTICLES }, (_, i) => ({
  a: random(i + 2) * Math.PI * 2,
  z: (random(i + 40) - 0.5) * 0.35,
  r: 0.76 + (random(i + 80) - 0.5) * 0.17,
  phase: random(i + 120) * 6.28,
  size: 0.38 + random(i + 160) * 1.03,
  shade: random(i + 200),
}));

function ParticleRing({ level }: { level: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const levelRef = useRef(0);
  useEffect(() => {
    levelRef.current = Math.max(0, Math.min(1, Number.isFinite(level) ? level : 0));
  }, [level]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;
    let raf = 0;
    let width = 1, height = 1, dpr = 1;
    let previous = performance.now(), tick = 0, smoothed = 0;
    const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
    let visible = true;
    const resize = () => {
      const box = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      width = Math.max(1, Math.round(box.width * dpr));
      height = Math.max(1, Math.round(box.height * dpr));
      canvas.width = width;
      canvas.height = height;
    };
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    resize();
    const handleVisibility = () => { visible = document.visibilityState === "visible"; previous = performance.now(); };
    document.addEventListener("visibilitychange", handleVisibility);
    const render = (now: number) => {
      const dt = Math.min(0.06, (now - previous) / 1000);
      previous = now;
      if (!visible) { raf = requestAnimationFrame(render); return; }
      if (!motionPreference.matches) tick += dt;
      const target = levelRef.current;
      smoothed += (target - smoothed) * (1 - Math.exp(-dt * (target > smoothed ? 4.0 : 2.7)));
      ctx.fillStyle = "#111214";
      ctx.fillRect(0, 0, width, height);
      const cx = width * 0.5, cy = height * 0.53;
      const unit = Math.min(width * 0.52, height * 0.58);
      const tilt = 0.97 + Math.sin(tick * 0.28) * 0.11;
      const rotation = tick * 0.25;
      const scale = 1 + smoothed * 0.17;
      const rendered: number[][] = [];
      for (const p of particles) {
        const angle = p.a + rotation + p.z * 0.09;
        const radius = p.r * scale * (1 + 0.055 * Math.sin(tick * 1.4 + p.phase)
          + smoothed * 0.023 * Math.sin(p.a * 6 + tick * 2.4));
        const x = Math.cos(angle) * radius;
        const z = Math.sin(angle) * radius;
        const y = z * Math.cos(tilt) - p.z * Math.sin(tilt);
        const depth = z * Math.sin(tilt) + p.z * Math.cos(tilt);
        const perspective = 1 / (1 - depth * 0.35);
        const sx = cx + x * unit * perspective;
        const sy = cy + y * unit * 0.76 * perspective;
        if (sx < -3 || sx > width + 3 || sy < -3 || sy > height + 3) continue;
        rendered.push([depth, sx, sy, p.size * (0.75 + perspective) * dpr * (1 + smoothed * 0.12), p.shade, 0.19 + 0.58 * (depth + 1) / 2]);
      }
      rendered.sort((a, b) => a[0] - b[0]);
      ctx.globalCompositeOperation = "source-over";
      for (const dot of rendered) {
        const rgb = dot[4] > 0.84 ? "243,239,232" : dot[4] > 0.53 ? "213,209,203" : dot[4] > 0.20 ? "181,183,187" : "134,139,146";
        ctx.fillStyle = `rgba(${rgb},${Math.min(0.95, dot[5] + smoothed * 0.09)})`;
        ctx.beginPath();
        ctx.arc(dot[1], dot[2], Math.max(0.35, dot[3]), 0, Math.PI * 2);
        ctx.fill();
      }
      raf = requestAnimationFrame(render);
    };
    raf = requestAnimationFrame(render);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); document.removeEventListener("visibilitychange", handleVisibility); };
  }, []);

  return <canvas ref={canvasRef} className="me2-call-particles" role="img" aria-label="Soft ivory particles rotating in response to future-self audio" />;
}

export default function FutureCallPage({
  aiAudioLevel = 0,
  connected = true,
  muted = false,
  onToggleMute,
  onEndCall,
  caption,
}: FutureCallPageProps) {
  const [seconds, setSeconds] = useState(0);
  const [ending, setEnding] = useState(false);
  useEffect(() => {
    if (!connected || ending) return;
    const startedAt = Date.now();
    const interval = window.setInterval(() => setSeconds(Math.floor((Date.now() - startedAt) / 1000)), 250);
    return () => window.clearInterval(interval);
  }, [connected, ending]);
  const time = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  const endCall = async () => {
    if (ending) return;
    setEnding(true);
    try { await onEndCall?.(); } catch { setEnding(false); }
  };
  return (
    <main className="me2-call-page">
      <header className="me2-call-header">
        <span className="me2-call-brand">Me²</span>
        <div className="me2-call-connection"><span className={`me2-call-indicator ${connected && !ending ? "is-live" : ""}`} />{ending ? "ENDING" : connected ? "CONNECTED" : "CONNECTING"}<time>{time}</time></div>
      </header>
      <section className="me2-call-stage" aria-label="Future Self Call">
        <div className="me2-call-intro"><p className="me2-call-eyebrow">A CONVERSATION ACROSS TIME</p><h1>Your Future Self</h1><p>Tomorrow is listening.</p></div>
        <div className="me2-call-visual"><ParticleRing level={connected && !ending ? aiAudioLevel : 0} /></div>
        <div className="me2-call-bottomcopy" aria-live="polite">{caption || (ending ? "Ending call…" : connected ? "You're connected to your future self." : "Establishing connection…")}</div>
      </section>
      <nav className="me2-call-actions" aria-label="Call controls">
        <button type="button" className={`me2-call-action ${muted ? "is-muted" : ""}`} onClick={onToggleMute} disabled={!connected || ending || !onToggleMute} aria-pressed={muted} aria-label={muted ? "Unmute microphone" : "Mute microphone"}>
          <span className="me2-call-action-circle">{muted ? <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 4 16 16M9 9v3a3 3 0 0 0 4.4 2.65M15 9V6a3 3 0 0 0-5.7-1.3M5 11v1a7 7 0 0 0 12 4.9M19 11v1a7 7 0 0 1-.5 2.6M12 19v3m-4 0h8"/></svg> : <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v4m-4 0h8"/></svg>}</span>
          <span>{muted ? "Unmute" : "Mute"}</span>
        </button>
        <button type="button" className="me2-call-action me2-call-hangup" onClick={endCall} disabled={ending} aria-label="End call">
          <span className="me2-call-action-circle"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.2 14.6c5.8-5.2 11.8-5.2 17.6 0l-2.3 3.6c-.3.5-.8.7-1.4.5l-2.7-1c-.6-.2-.9-.6-.9-1.2v-1.5c-1-.3-2-.3-3 0v1.5c0 .6-.3 1-.9 1.2l-2.7 1c-.6.2-1.1 0-1.4-.5l-2.3-3.6Z"/></svg></span>
          <span>End Call</span>
        </button>
      </nav>
      <p className="me2-call-disclaimer">Me² explores possible futures. It does not predict them.</p>
    </main>
  );
}
