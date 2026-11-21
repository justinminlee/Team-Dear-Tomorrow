/**
 * The future-self phone call, in the browser.
 *
 *   prepare()  mic permission + the AI's opening line, in parallel
 *   begin()    play the opening line, then take turns:
 *              listen → (user speaks, then pauses) → send WAV → AI replies → play → listen …
 *   end()      stop everything, return the call length
 *
 * Turn-taking is hands-free: a simple voice-activity detector starts recording
 * when the user speaks and sends the turn after ~0.9 s of silence. The mic is
 * ignored while the AI is talking, so it never hears itself.
 */
import { ApiError } from "../api/auth";
import { callApi, type ChatMessage, type SpokenReply } from "../api/call";

export type CallPhase =
  | "idle"
  | "preparing" // asking for the mic, fetching the opening line
  | "ready"     // waiting for begin()
  | "listening" // waiting for the user to speak
  | "hearing"   // recording the user
  | "thinking"  // waiting for the reply
  | "speaking"  // playing the reply
  | "ended"
  | "failed";

export type CallSnapshot = {
  phase: CallPhase;
  muted: boolean;
  /** What the future self is saying, or a short status/apology. */
  caption: string;
  /** Why the call could not start (phase "failed"). */
  error: string;
};

export const INITIAL_SNAPSHOT: CallSnapshot = { phase: "idle", muted: false, caption: "", error: "" };

// Voice-activity detection, in milliseconds.
const SPEECH_START_MS = 120; // loud this long = the user started talking
const END_SILENCE_MS = 900;  // quiet this long after speech = their turn is over
const MIN_SPEECH_MS = 300;   // shorter bursts (a cough, a click) are ignored
const MAX_TURN_MS = 30_000;  // send long monologues anyway
const PREROLL_MS = 300;      // keep audio from just before speech was detected
const MIN_THRESHOLD = 0.015; // RMS; raised automatically in noisy rooms

const TARGET_RATE = 16_000; // what the speech-to-text API expects

const SORRY = "Sorry, the line broke up for a moment. Could you say that again?";

// Collects mic samples off the main thread and posts them in blocks of 2048.
const MIC_TAP_WORKLET = `
class Me2MicTap extends AudioWorkletProcessor {
  constructor() { super(); this.buf = new Float32Array(2048); this.n = 0; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) for (let i = 0; i < ch.length; i++) {
      this.buf[this.n++] = ch[i];
      if (this.n === this.buf.length) { this.port.postMessage(this.buf.slice(0)); this.n = 0; }
    }
    return true;
  }
}
registerProcessor("me2-mic-tap", Me2MicTap);
`;

export class FutureCall {
  private state: CallSnapshot = INITIAL_SNAPSHOT;
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private tap: AudioWorkletNode | null = null;
  private output: AnalyserNode | null = null;
  private playing: AudioBufferSourceNode | null = null;
  private opening: { buffer: AudioBuffer; text: string } | null = null;
  private history: ChatMessage[] = [];
  private startedAt = 0;
  private turn = 0; // bumped on end() so late replies are dropped
  private levelData = new Float32Array(1024);

  // Voice-activity detection state
  private preroll: Float32Array[] = [];
  private recorded: Float32Array[] = [];
  private loudMs = 0;
  private speechMs = 0;
  private silenceMs = 0;
  private recordedMs = 0;
  private noiseFloor = 0.004;

  private readonly onChange: (snapshot: CallSnapshot) => void;
  private readonly onAuthError: () => void;

  constructor(onChange: (snapshot: CallSnapshot) => void, onAuthError: () => void) {
    this.onChange = onChange;
    this.onAuthError = onAuthError;
  }

  /** Must be called from a click handler: browsers only allow audio started by a user gesture. */
  prepare(): Promise<void> {
    if (this.state.phase !== "idle") return Promise.resolve();
    // Created synchronously, inside the gesture, so Safari lets it play later.
    this.ctx = new AudioContext();
    void this.ctx.resume();
    this.set({ phase: "preparing", error: "" });
    return this.setup();
  }

  /** Play the opening line and start taking turns. */
  begin(): void {
    if (this.state.phase !== "ready" || !this.opening) return;
    this.startedAt = Date.now();
    this.history.push({ role: "assistant", content: this.opening.text });
    this.play(this.opening.buffer, this.opening.text);
    this.opening = null;
  }

  setMuted(muted: boolean): void {
    this.stream?.getAudioTracks().forEach((track) => (track.enabled = !muted));
    this.set({ muted });
    if (muted && this.state.phase === "hearing") this.listen(); // drop the half-recorded turn
  }

  /** Hang up. Returns the call length in seconds. */
  end(): number {
    const seconds = this.startedAt ? Math.round((Date.now() - this.startedAt) / 1000) : 0;
    this.turn++;
    this.release();
    if (this.state.phase !== "failed") this.set({ phase: "ended", caption: "" });
    return seconds;
  }

  /** Loudness of the AI's voice right now, 0..1, for the visualisation. */
  level(): number {
    if (this.state.phase !== "speaking" || !this.output) return 0;
    this.output.getFloatTimeDomainData(this.levelData);
    return Math.min(1, rms(this.levelData) * 5);
  }

  // ---------- setup ----------

  private async setup() {
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("This browser can't use a microphone here. Open the site over HTTPS in Chrome or Safari.");
      }
      const [stream, start] = await Promise.all([
        navigator.mediaDevices
          .getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } })
          .catch((err: unknown) => {
            throw new Error(microphoneProblem(err));
          }),
        callApi.start(),
      ]);
      if (this.state.phase !== "preparing" || !this.ctx) {
        stream.getTracks().forEach((t) => t.stop()); // hung up while connecting
        return;
      }
      this.stream = stream;
      const ctx = this.ctx;

      const url = URL.createObjectURL(new Blob([MIC_TAP_WORKLET], { type: "application/javascript" }));
      try {
        await ctx.audioWorklet.addModule(url);
      } finally {
        URL.revokeObjectURL(url);
      }
      const mic = ctx.createMediaStreamSource(stream);
      this.tap = new AudioWorkletNode(ctx, "me2-mic-tap");
      this.tap.port.onmessage = (event: MessageEvent<Float32Array>) => this.onMicFrame(event.data);
      const silent = ctx.createGain(); // keeps the worklet running without playing the mic back
      silent.gain.value = 0;
      mic.connect(this.tap).connect(silent).connect(ctx.destination);

      this.output = ctx.createAnalyser();
      this.output.fftSize = 1024;
      this.output.connect(ctx.destination);

      this.opening = { buffer: await this.decode(start.reply), text: start.reply.text };
      if (this.state.phase === "preparing") this.set({ phase: "ready" });
    } catch (err) {
      if (this.state.phase !== "preparing") return;
      if (err instanceof ApiError && err.status === 401) this.onAuthError();
      this.release();
      this.set({ phase: "failed", error: err instanceof Error ? err.message : "Something went wrong." });
    }
  }

  private release() {
    try {
      this.playing?.stop();
    } catch {
      /* already stopped */
    }
    this.playing = null;
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    if (this.tap) this.tap.port.onmessage = null;
    this.tap?.disconnect();
    this.tap = null;
    if (this.ctx && this.ctx.state !== "closed") void this.ctx.close();
    this.ctx = null;
    this.output = null;
  }

  // ---------- turn-taking ----------

  private listen(caption = "") {
    this.preroll = [];
    this.recorded = [];
    this.loudMs = this.speechMs = this.silenceMs = this.recordedMs = 0;
    this.set({ phase: "listening", caption });
  }

  private onMicFrame(frame: Float32Array) {
    const { phase, muted } = this.state;
    if (muted || (phase !== "listening" && phase !== "hearing") || !this.ctx) return;
    const ms = (frame.length / this.ctx.sampleRate) * 1000;
    const level = rms(frame);
    const threshold = Math.max(MIN_THRESHOLD, this.noiseFloor * 3);
    const loud = level > threshold;

    if (phase === "listening") {
      this.preroll.push(frame);
      while (this.preroll.length * ms > PREROLL_MS) this.preroll.shift();
      if (loud) this.loudMs += ms;
      else {
        this.loudMs = 0;
        this.noiseFloor = this.noiseFloor * 0.95 + level * 0.05; // learn the room's background noise
      }
      if (this.loudMs >= SPEECH_START_MS) {
        this.recorded = this.preroll;
        this.preroll = [];
        this.recordedMs = this.recorded.length * ms;
        this.speechMs = this.loudMs;
        this.silenceMs = 0;
        this.set({ phase: "hearing", caption: "" });
      }
      return;
    }

    // hearing
    this.recorded.push(frame);
    this.recordedMs += ms;
    if (loud) {
      this.speechMs += ms;
      this.silenceMs = 0;
    } else {
      this.silenceMs += ms;
    }
    if (this.silenceMs >= END_SILENCE_MS || this.recordedMs >= MAX_TURN_MS) void this.sendTurn();
  }

  private async sendTurn() {
    if (!this.ctx) return;
    const samples = this.recorded;
    const enoughSpeech = this.speechMs >= MIN_SPEECH_MS;
    this.recorded = [];
    if (!enoughSpeech) {
      this.listen();
      return;
    }
    const wav = encodeWav(downsample(concat(samples), this.ctx.sampleRate, TARGET_RATE), TARGET_RATE);
    const turn = this.turn;
    this.set({ phase: "thinking", caption: "" });
    try {
      const { heard, reply } = await callApi.turn(wav, this.history);
      if (turn !== this.turn) return; // hung up meanwhile
      if (!heard || !reply) {
        this.listen();
        return;
      }
      const buffer = await this.decode(reply);
      if (turn !== this.turn) return;
      this.history.push({ role: "user", content: heard }, { role: "assistant", content: reply.text });
      this.play(buffer, reply.text);
    } catch (err) {
      if (turn !== this.turn) return;
      if (err instanceof ApiError && err.status === 401) {
        this.onAuthError();
        return;
      }
      this.listen(SORRY);
    }
  }

  private play(buffer: AudioBuffer, text: string) {
    if (!this.ctx || !this.output) return;
    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(this.output);
    source.onended = () => {
      if (this.playing === source && this.state.phase === "speaking") {
        this.playing = null;
        this.listen();
      }
    };
    this.playing = source;
    this.set({ phase: "speaking", caption: text });
    source.start();
  }

  private async decode(reply: SpokenReply): Promise<AudioBuffer> {
    if (!this.ctx) throw new Error("The call has ended.");
    const bytes = Uint8Array.from(atob(reply.audio), (c) => c.charCodeAt(0));
    return this.ctx.decodeAudioData(bytes.buffer);
  }

  private set(patch: Partial<CallSnapshot>) {
    this.state = { ...this.state, ...patch };
    this.onChange(this.state);
  }
}

// ---------- audio helpers ----------

function microphoneProblem(err: unknown): string {
  const name = err instanceof DOMException ? err.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "Microphone access is blocked. Allow the microphone for this site in your browser's address bar, then try again.";
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") return "No microphone was found on this device.";
  if (name === "NotReadableError") return "Your microphone is being used by another app. Close it and try again.";
  return "We couldn't start your microphone.";
}

export function rms(samples: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
  return Math.sqrt(sum / Math.max(1, samples.length));
}

export function concat(chunks: Float32Array[]): Float32Array {
  const out = new Float32Array(chunks.reduce((n, c) => n + c.length, 0));
  let offset = 0;
  for (const c of chunks) {
    out.set(c, offset);
    offset += c.length;
  }
  return out;
}

/** Average-and-pick downsampling (the averaging doubles as a simple low-pass filter). */
export function downsample(input: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return input;
  const ratio = fromRate / toRate;
  const out = new Float32Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(input.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += input[j];
    out[i] = sum / Math.max(1, end - start);
  }
  return out;
}

/** 16-bit mono PCM WAV. */
export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const text = (offset: number, s: string) => [...s].forEach((ch, i) => view.setUint8(offset + i, ch.charCodeAt(0)));
  text(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true); // fmt chunk size
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}
