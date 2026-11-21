import { useCallback, useEffect, useRef, useState } from "react";
import "./ConnectingPage.css";

/**
 * Me² AI connecting page.
 * The parent should set `connected` to true when the real AI/backend session is ready.
 * The page never initiates or simulates an AI connection by itself.
 * Visual theme: charcoal + warm ivory, shared with Me² Landing/Login.
 */
export interface ConnectingPageProps {
  connected?: boolean;
  onConnected?: () => void;
  onAudioError?: (error: Error) => void;
  /** Shown instead of the connecting copy when the call could not be set up. */
  error?: string;
  /** Leave the connecting screen (shown with an error). */
  onCancel?: () => void;
}

type BrowserAudioContext = AudioContext;
const DIAL_NUMBER = "8666776963"; // TOMORROW ME on a standard telephone keypad
const DTMF: Record<string, [number, number]> = {
  "1": [697, 1209], "2": [697, 1336], "3": [697, 1477],
  "4": [770, 1209], "5": [770, 1336], "6": [770, 1477],
  "7": [852, 1209], "8": [852, 1336], "9": [852, 1477],
  "*": [941, 1209], "0": [941, 1336], "#": [941, 1477],
};

export default function ConnectingPage({
  connected = false,
  onConnected,
  onAudioError,
  error,
  onCancel,
}: ConnectingPageProps) {
  const contextRef = useRef<BrowserAudioContext | null>(null);
  const masterRef = useRef<GainNode | null>(null);
  const timerRef = useRef<number | null>(null);
  const startedRef = useRef(false);
  const nextRingRef = useRef(0);
  const playingRef = useRef(false);
  const connectedRef = useRef(connected);
  const pendingRef = useRef(false);
  const [playing, setPlaying] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    connectedRef.current = connected;
  }, [connected]);

  const stopScheduler = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const scheduleTones = useCallback(
    (frequencies: number[], startAt: number, duration: number, volume = 0.03) => {
      const audio = contextRef.current;
      const master = masterRef.current;
      if (!audio || !master) return;
      const envelope = audio.createGain();
      const attack = Math.min(0.009, duration / 4);
      const release = Math.min(0.018, duration / 4);
      envelope.gain.setValueAtTime(0.0001, startAt);
      envelope.gain.linearRampToValueAtTime(volume, startAt + attack);
      envelope.gain.setValueAtTime(volume, startAt + duration - release);
      envelope.gain.linearRampToValueAtTime(0.0001, startAt + duration);
      envelope.connect(master);
      frequencies.forEach((freq) => {
        const oscillator = audio.createOscillator();
        oscillator.type = "sine";
        oscillator.frequency.value = freq;
        oscillator.connect(envelope);
        oscillator.start(startAt);
        oscillator.stop(startAt + duration + 0.02);
        oscillator.onended = () => oscillator.disconnect();
      });
      // The gain node is small and will be garbage-collected after the oscillators end.
    },
    [],
  );

  const scheduleRinging = useCallback(() => {
    const audio = contextRef.current;
    if (!playingRef.current || connectedRef.current || !audio || audio.state !== "running") return;
    while (nextRingRef.current < audio.currentTime + 0.18) {
      scheduleTones([440, 480], nextRingRef.current, 0.38, 0.026);
      scheduleTones([440, 480], nextRingRef.current + 0.48, 0.38, 0.026);
      nextRingRef.current += 3.25;
    }
  }, [scheduleTones]);

  const toggleSound = useCallback(async () => {
    if (connectedRef.current || pendingRef.current) return;
    pendingRef.current = true;
    setBusy(true);
    try {
      if (!contextRef.current) {
        const audio = new AudioContext();
        const master = audio.createGain();
        master.gain.value = 0.85;
        master.connect(audio.destination);
        contextRef.current = audio;
        masterRef.current = master;
      }
      const audio = contextRef.current;
      if (playingRef.current) {
        // Suspending the audio clock preserves the exact point in dialling/ringing.
        playingRef.current = false;
        await audio.suspend();
        setPlaying(false);
      } else {
        await audio.resume();
        if (!startedRef.current) {
          startedRef.current = true;
          let time = audio.currentTime + 0.09;
          for (const digit of DIAL_NUMBER) {
            scheduleTones(DTMF[digit], time, 0.105, 0.032);
            time += 0.16;
          }
          nextRingRef.current = time + 0.18;
        }
        playingRef.current = true;
        setPlaying(true);
        if (timerRef.current === null) {
          timerRef.current = window.setInterval(scheduleRinging, 90);
        }
        scheduleRinging();
      }
    } catch (error) {
      const normalized = error instanceof Error ? error : new Error(String(error));
      onAudioError?.(normalized);
      console.error("Me² Connecting audio error:", normalized);
    } finally {
      pendingRef.current = false;
      setBusy(false);
    }
  }, [onAudioError, scheduleRinging, scheduleTones]);

  // Stop audio immediately when the real connection succeeds.
  useEffect(() => {
    if (!connected && !error) return;
    playingRef.current = false;
    stopScheduler();
    const audio = contextRef.current;
    if (audio && audio.state === "running") void audio.suspend();
    if (connected) onConnected?.();
  }, [connected, error, onConnected, stopScheduler]);

  // Close the audio context and timers when navigating away.
  useEffect(() => () => {
    playingRef.current = false;
    stopScheduler();
    const audio = contextRef.current;
    contextRef.current = null;
    masterRef.current = null;
    if (audio && audio.state !== "closed") void audio.close();
  }, [stopScheduler]);

  return (
    <div className="me2-connecting-page">
      <header className="me2-connecting-header">
        <span className="me2-connecting-logo">Me²</span>
        <span className="me2-connecting-eyebrow">A call across time</span>
      </header>

      <main className="me2-connecting-main" aria-live="polite">
        <div className="me2-connecting-dots" aria-hidden="true" style={{ visibility: connected || error ? "hidden" : "visible" }}>
          <span className="me2-connecting-dot" />
          <span className="me2-connecting-dot" />
          <span className="me2-connecting-dot" />
        </div>
        {error ? (
          <>
            <p className="me2-connecting-status">Connection failed</p>
            <h1>We couldn't reach your future self.</h1>
            <p className="me2-connecting-description" role="alert">{error}</p>
          </>
        ) : (
          <>
            <p className="me2-connecting-status">{connected ? "Connection ready" : "Establishing connection"}</p>
            <h1>{connected ? "Your future self is calling." : "Connecting to your future self..."}</h1>
            <p className="me2-connecting-description">
              {connected ? "Your conversation is ready to begin." : "A conversation across time is about to begin."}
            </p>
          </>
        )}
      </main>

      <section className="me2-connecting-sound" aria-label="Audio controls">
        {error ? (
          <button type="button" className="me2-connecting-sound-button" onClick={onCancel} disabled={!onCancel}>
            GO BACK
          </button>
        ) : (
        <button
          type="button"
          className="me2-connecting-sound-button"
          onClick={toggleSound}
          disabled={connected || busy}
          aria-pressed={playing && !connected}
        >
          {connected ? "CONNECTION COMPLETE" : playing ? "MUTE" : "SOUND ON"}
        </button>
        )}
        {!error && <p>Tap Sound On to hear the dialling sequence. Tap Mute to pause.</p>}
      </section>
      <footer className="me2-connecting-footer">Your future is a possibility, not a prediction.</footer>
    </div>
  );
}
