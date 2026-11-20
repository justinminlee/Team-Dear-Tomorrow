import { useEffect, useRef, useState } from "react";
import "./FutureCallPage.css";

/**
 * Me² Future Self Call — Smooth v5
 * Standalone React + TypeScript component with no runtime dependencies.
 * The audio-reactive particle canvas uses the Web Audio API.
 *
 * For real AI voice playback: pass the AI audio HTMLMediaElement through aiAudioElement.
 * This is an integration hook, not an implemented AI API connection.
 */
export type FutureCallPageProps = {
  aiAudioElement?: HTMLMediaElement | null;
  onEndCall?: () => void;
};

type Particle = {
  angle: number; z: number; radius: number; phase: number;
  size: number; shade: number;
};

type AudioMode = "idle" | "demo" | "mic" | "file" | "ai";
const COUNT = 2200;
const rand = (seed: number) => {
  const n = Math.sin(seed * 127.1 + 12.85) * 43758.5453;
  return n - Math.floor(n);
};
const PARTICLES: Particle[] = Array.from({ length: COUNT }, (_, i) => ({
  angle: rand(i + 2) * Math.PI * 2,
  z: (rand(i + 40) - 0.5) * 0.35,
  radius: 0.76 + (rand(i + 80) - 0.5) * 0.17,
  phase: rand(i + 120) * 6.28,
  size: 0.38 + rand(i + 160) * 1.03,
  shade: rand(i + 200),
}));

export default function FutureCallPage({ aiAudioElement, onEndCall }: FutureCallPageProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState("Ambient motion · Select a sound source below");
  const [mode, setMode] = useState<AudioMode>("idle");
  const [muted, setMuted] = useState(false);
  const [ended, setEnded] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [audioVisible, setAudioVisible] = useState(false);
  const audioEngine = useRef<{
    context: AudioContext | null;
    analyser: AnalyserNode | null;
    data: Uint8Array<ArrayBuffer> | null;
    source: AudioNode | null;
    stream: MediaStream | null;
    mediaSource: MediaElementAudioSourceNode | null;
    mediaSourceElement: HTMLMediaElement | null;
    demoMaster: GainNode | null;
    demoNodes: OscillatorNode[];
    demoTimer: number | null;
    objectUrl: string | null;
    mode: AudioMode;
    muted: boolean;
    ended: boolean;
  }>({
    context: null, analyser: null, data: null, source: null, stream: null,
    mediaSource: null, mediaSourceElement: null, demoMaster: null,
    demoNodes: [], demoTimer: null, objectUrl: null,
    mode: "idle", muted: false, ended: false,
  });

  function changeMode(next: AudioMode) {
    audioEngine.current.mode = next;
    setMode(next);
  }

  async function ensureAudio() {
    const e = audioEngine.current;
    if (!e.context) {
      e.context = new AudioContext();
      e.analyser = e.context.createAnalyser();
      e.analyser.fftSize = 1024;
      e.analyser.smoothingTimeConstant = 0.75;
      e.data = new Uint8Array(e.analyser.fftSize);
    }
    await e.context.resume();
    return e;
  }

  function stopSources() {
    const e = audioEngine.current;
    if (e.demoTimer !== null) window.clearInterval(e.demoTimer);
    e.demoTimer = null;
    e.demoNodes.forEach((node) => { try { node.stop(); } catch { /* already stopped */ } });
    e.demoNodes = [];
    e.demoMaster?.disconnect();
    e.demoMaster = null;
    e.stream?.getTracks().forEach((track) => track.stop());
    e.stream = null;
    e.source?.disconnect();
    e.source = null;
    e.mediaSource?.disconnect();
    if (e.mediaSourceElement && e.mediaSourceElement === audioRef.current) audioRef.current?.pause();
    e.analyser?.disconnect();
    changeMode("idle");
    setAudioVisible(false);
  }

  async function startDemo() {
    const e = audioEngine.current;
    if (e.ended) return;
    if (e.mode === "demo") {
      stopSources();
      setStatus("Ambient motion · Demo stopped");
      return;
    }
    stopSources();
    try {
      await ensureAudio();
      if (e.ended) return;
      const ctx = e.context!;
      const master = ctx.createGain();
      master.gain.value = e.muted ? 0 : 0.055;
      master.connect(e.analyser!);
      e.analyser!.connect(ctx.destination);
      e.demoMaster = master;
      changeMode("demo");
      function note() {
        if (e.mode !== "demo") return;
        const now = ctx.currentTime;
        const duration = 0.32 + Math.random() * 0.16;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(160 + Math.random() * 140, now);
        osc.frequency.exponentialRampToValueAtTime(85 + Math.random() * 55, now + duration);
        gain.gain.setValueAtTime(0.0001, now);
        gain.gain.exponentialRampToValueAtTime(0.28, now + 0.09);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
        osc.connect(gain).connect(master);
        osc.start(now);
        osc.stop(now + duration + 0.05);
        e.demoNodes.push(osc);
        osc.onended = () => {
          e.demoNodes = e.demoNodes.filter((v) => v !== osc);
          osc.disconnect(); gain.disconnect();
        };
      }
      note();
      e.demoTimer = window.setInterval(note, 420);
      setStatus("Demo sound · Particles react to audio");
    } catch {
      setStatus("Audio unavailable · Check browser sound permissions");
    }
  }

  async function startMic() {
    const e = audioEngine.current;
    if (e.ended) return;
    if (e.mode === "mic") {
      stopSources(); setStatus("Ambient motion · Microphone stopped"); return;
    }
    stopSources();
    try {
      await ensureAudio();
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (e.ended) { stream.getTracks().forEach((t) => t.stop()); return; }
      e.stream = stream;
      e.source = e.context!.createMediaStreamSource(stream);
      e.source.connect(e.analyser!);
      // Do NOT route microphone audio to the speakers to avoid feedback.
      changeMode("mic");
      setStatus("Microphone listening · Speak to move the particles");
    } catch {
      setStatus("Microphone unavailable · Allow mic access on HTTPS or localhost");
    }
  }

  async function attachAudioElement(element: HTMLMediaElement, nextMode: "file" | "ai") {
    const e = await ensureAudio();
    // A given HTMLMediaElement may only be passed once to createMediaElementSource.
    // Reuse the node if the element remains the same.
    if (e.mediaSource && e.mediaSourceElement !== element) {
      throw new Error("A new media element requires a new MediaElementAudioSourceNode.");
    }
    if (!e.mediaSource) {
      e.mediaSource = e.context!.createMediaElementSource(element);
      e.mediaSourceElement = element;
    }
    e.mediaSource.connect(e.analyser!);
    e.analyser!.connect(e.context!.destination);
    element.muted = e.muted;
    changeMode(nextMode);
  }

  async function uploadFile(file: File | undefined) {
    if (!file || audioEngine.current.ended || !audioRef.current) return;
    stopSources();
    const e = audioEngine.current;
    if (e.objectUrl) URL.revokeObjectURL(e.objectUrl);
    e.objectUrl = URL.createObjectURL(file);
    const el = audioRef.current;
    el.src = e.objectUrl;
    setAudioVisible(true);
    try {
      await attachAudioElement(el, "file");
      setStatus(`Audio file · ${file.name}`);
      await el.play();
    } catch {
      setStatus("Audio loaded · Press play in player to start");
    }
  }

  function toggleMute() {
    const e = audioEngine.current;
    const next = !e.muted;
    e.muted = next;
    setMuted(next);
    if (e.mode === "demo" && e.demoMaster && e.context) {
      e.demoMaster.gain.setTargetAtTime(next ? 0 : 0.055, e.context.currentTime, 0.035);
    } else if (e.mode === "file" && audioRef.current) {
      audioRef.current.muted = next;
    } else if (e.mode === "ai" && e.mediaSourceElement) {
      e.mediaSourceElement.muted = next;
    } else if (e.mode === "mic") {
      setStatus(next ? "Microphone visualisation muted" : "Microphone listening · Speak to move the particles");
    }
  }

  function endCall() {
    stopSources();
    const e = audioEngine.current;
    e.ended = true;
    setEnded(true);
    setStatus("Call ended · Demo complete");
    void e.context?.suspend();
    onEndCall?.();
  }

  // If a stable AI audio element is provided, it can drive the visualisation.
  // The integration layer must provide and play the media element itself.
  useEffect(() => {
    if (!aiAudioElement) return;
    let cancelled = false;
    (async () => {
      try {
        stopSources();
        await attachAudioElement(aiAudioElement, "ai");
        if (!cancelled) setStatus("Future self voice · Audio reactive");
      } catch {
        if (!cancelled) setStatus("AI audio source unavailable · Check integration");
      }
    })();
    return () => { cancelled = true; };
    // Stable HTMLAudioElement should be created by the parent and passed unchanged.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aiAudioElement]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;
    let frame = 0;
    let w = 1, h = 1, dpr = 1;
    let tick = 0, amplitude = 0, last = performance.now();
    const started = performance.now();
    let lastTimeLabel = -1;
    const resize = () => {
      const r = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      w = canvas.width = Math.max(1, Math.floor(r.width * dpr));
      h = canvas.height = Math.max(1, Math.floor(r.height * dpr));
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);

    function getLevel() {
      const e = audioEngine.current;
      if (!e.analyser || !e.data || e.mode === "idle" || e.muted) return 0;
      e.analyser.getByteTimeDomainData(e.data);
      let squared = 0;
      for (let i = 0; i < e.data.length; i++) {
        const value = (e.data[i] - 128) / 128;
        squared += value * value;
      }
      return Math.min(0.75, Math.sqrt(squared / e.data.length) * 3);
    }

    function render(now: number) {
      if (!ctx) return;
      const dt = Math.min(60, now - last) / 1000;
      last = now;
      if (!audioEngine.current.ended) tick += dt;
      const target = getLevel();
      amplitude += (target - amplitude) * (1 - Math.exp(-dt * (target > amplitude ? 4 : 2.7)));
      ctx.fillStyle = "#0B0B0D";
      ctx.fillRect(0, 0, w, h);
      const centerX = w * 0.5, centerY = h * 0.57;
      const unit = Math.min(w * 0.52, h * 0.58);
      const tilt = 0.97 + Math.sin(tick * 0.28) * 0.11;
      const rotation = tick * 0.25; // steady rotation independent of audio
      const scale = 1 + amplitude * 0.17;
      const ordered: Array<[number, number, number, number, number, number]> = [];
      for (const p of PARTICLES) {
        const angle = p.angle + rotation + p.z * 0.09;
        const radial = p.radius * scale *
          (1 + 0.055 * Math.sin(tick * 1.4 + p.phase) + amplitude * 0.023 * Math.sin(p.angle * 6 + tick * 2.4));
        const x = Math.cos(angle) * radial;
        const z = Math.sin(angle) * radial;
        const y = z * Math.cos(tilt) - p.z * Math.sin(tilt);
        const depth = z * Math.sin(tilt) + p.z * Math.cos(tilt);
        const perspective = 1 / (1 - depth * 0.35);
        const sx = centerX + x * unit * perspective;
        const sy = centerY + y * unit * 0.76 * perspective;
        if (sx < 0 || sx > w || sy < 0 || sy > h) continue;
        ordered.push([depth, sx, sy, p.size * (0.75 + perspective) * dpr * (1 + amplitude * 0.12), p.shade,
          0.2 + 0.56 * (depth + 1) / 2]);
      }
      ordered.sort((a, b) => a[0] - b[0]);
      ctx.globalCompositeOperation = "lighter";
      for (const p of ordered) {
        ctx.beginPath();
        const rgb = p[4] > 0.9 ? "242,237,230" : p[4] > 0.57 ? "232,184,126" : p[4] > 0.22 ? "199,123,67" : "153,91,52";
        ctx.fillStyle = `rgba(${rgb},${Math.min(0.95, p[5] + amplitude * 0.1)})`;
        ctx.arc(p[1], p[2], Math.max(0.35, p[3]), 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
      if (!audioEngine.current.ended) {
        const elapsed = Math.floor((now - started) / 1000);
        if (elapsed !== lastTimeLabel) {
          lastTimeLabel = elapsed;
          setSeconds(elapsed);
        }
      }
      frame = requestAnimationFrame(render);
    }
    frame = requestAnimationFrame(render);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      const e = audioEngine.current;
      if (e.demoTimer !== null) window.clearInterval(e.demoTimer);
      e.demoNodes.forEach((n) => { try { n.stop(); } catch { /* noop */ } });
      e.stream?.getTracks().forEach((track) => track.stop());
      e.mediaSource?.disconnect();
      e.source?.disconnect();
      e.analyser?.disconnect();
      if (e.objectUrl) URL.revokeObjectURL(e.objectUrl);
      void e.context?.close();
      e.context = null;
      e.ended = false;
    };
  }, []);

  const time = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  return (
    <main className="me2-call">
      <header className="me2-call__header">
        <div className="me2-call__logo">Me²</div>
        <div className="me2-call__connection"><span className="me2-call__led"/> CONNECTED <span>{time}</span></div>
      </header>
      <section className="me2-call__hero" aria-label="Future-self audio visualisation">
        <div className="me2-call__heading"><p className="me2-call__eyebrow">A CALL ACROSS TIME</p>
          <h1>Your Future Self</h1><p className="me2-call__subtitle">Tomorrow is listening.</p></div>
        <div className="me2-call__canvas-wrap"><canvas ref={canvasRef} aria-label="Rotating amber audio-reactive particle ring"/></div>
        <div className="me2-call__audio-status" aria-live="polite">{status}</div>
      </section>
      <section className="me2-call__panel">
        <p className="me2-call__panel-title">Audio reactive preview</p>
        <div className="me2-call__actions">
          <button type="button" className={`me2-call__btn ${mode === "demo" ? "is-active" : ""}`} onClick={startDemo} disabled={ended}>▶ Demo sound</button>
          <button type="button" className={`me2-call__btn ${mode === "mic" ? "is-active" : ""}`} onClick={startMic} disabled={ended}>🎙 Use microphone</button>
          <button type="button" className="me2-call__btn" disabled={ended} onClick={() => fileRef.current?.click()}>♫ Upload audio</button>
          <input ref={fileRef} className="me2-call__file" type="file" accept="audio/*" onChange={(event) => uploadFile(event.target.files?.[0])}/>
          <button type="button" className={`me2-call__btn ${muted ? "is-active" : ""}`} onClick={toggleMute} disabled={ended}>{muted ? "Sound On" : "Mute"}</button>
          <button type="button" className="me2-call__btn me2-call__btn--end" onClick={endCall} disabled={ended}>{ended ? "Call Ended" : "End Call"}</button>
        </div>
        <p className="me2-call__hint">Optimised demo: smooth audio response, steady rotation and lightweight particle rendering. Microphone requires browser permission and HTTPS/localhost.</p>
        <audio ref={audioRef} controls className={audioVisible ? "me2-call__player" : "me2-call__file"}/>
      </section>
      <footer className="me2-call__footer">Concept prototype · Original Canvas particle animation, not Motion's vgpu implementation</footer>
    </main>
  );
}
