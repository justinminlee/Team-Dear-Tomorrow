import { useEffect, useRef, useState } from "react";

const MAX_SECONDS = 120;

type Status = "idle" | "recording" | "transcribing";

export interface VoiceAnswerProps {
  id: string;
  label: string;
  value: string;
  /** Called with the transcribed words, or with typed text when voice isn't available. */
  onChange: (text: string, spoken: boolean) => void;
  transcribe: (audio: Blob) => Promise<string>;
}

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"].find((t) =>
    MediaRecorder.isTypeSupported(t)
  );
}

/** Answer a question out loud: record, turn it into text, show the words. */
export default function VoiceAnswer({ id, label, value, onChange, transcribe }: VoiceAnswerProps) {
  const [status, setStatus] = useState<Status>("idle");
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");
  const [typing, setTyping] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const supported = typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && !!pickMimeType();

  const releaseMic = () => {
    window.clearInterval(timer.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
  };

  // Turn the microphone off if the user leaves the page mid-recording.
  useEffect(() => () => {
    if (recorder.current?.state === "recording") {
      recorder.current.onstop = null;
      recorder.current.stop();
    }
    releaseMic();
  }, []);

  const stop = () => {
    if (recorder.current?.state === "recording") recorder.current.stop();
  };

  const start = async () => {
    setError("");
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("Microphone access was blocked. Allow it in your browser's address bar, then try again.");
      return;
    }
    const chunks: Blob[] = [];
    const mimeType = pickMimeType();
    const rec = new MediaRecorder(stream.current, mimeType ? { mimeType } : undefined);
    rec.ondataavailable = (e) => e.data.size > 0 && chunks.push(e.data);
    rec.onstop = async () => {
      releaseMic();
      setStatus("transcribing");
      try {
        const words = await transcribe(new Blob(chunks, { type: rec.mimeType || "audio/webm" }));
        onChange(words, true);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Couldn't turn that into text. Please try again.");
      } finally {
        setStatus("idle");
      }
    };
    recorder.current = rec;
    rec.start();
    setSeconds(0);
    setStatus("recording");
    const startedAt = Date.now();
    timer.current = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      setSeconds(elapsed);
      if (elapsed >= MAX_SECONDS) stop(); // keep answers short enough to upload
    }, 250);
  };

  // Without a microphone the question can still be answered by typing.
  if (!supported || typing) {
    return (
      <div className="me2-voice">
        <textarea
          id={id}
          value={value}
          placeholder="Your answer…"
          maxLength={2000}
          aria-label={label}
          onChange={(e) => onChange(e.target.value, false)}
        />
        {!supported && <p className="me2-voice-hint">Voice recording isn't available in this browser, so type your answer.</p>}
        {supported && (
          <button type="button" className="me2-voice-link" onClick={() => setTyping(false)}>
            Answer out loud instead
          </button>
        )}
      </div>
    );
  }

  const time = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

  return (
    <div className="me2-voice" id={id} tabIndex={-1}>
      <div className="me2-voice-row">
        {status === "recording" ? (
          <button type="button" className="me2-voice-button is-recording" onClick={stop}>
            <span className="me2-voice-dot" aria-hidden="true" /> Stop · {time}
          </button>
        ) : (
          <button
            type="button"
            className="me2-voice-button"
            onClick={start}
            disabled={status === "transcribing"}
            aria-label={`${value ? "Record again" : "Record your answer"}: ${label}`}
          >
            <span className="me2-voice-mic" aria-hidden="true">🎙</span>
            {status === "transcribing" ? "Turning your words into text…" : value ? "Record again" : "Record your answer"}
          </button>
        )}
        {status === "idle" && (
          <button type="button" className="me2-voice-link" onClick={() => setTyping(true)}>
            Type instead
          </button>
        )}
      </div>

      <div className="me2-voice-text" aria-live="polite">
        {value ? <>“{value}”</> : <span className="me2-voice-empty">Press record and speak naturally — no need to be perfect.</span>}
      </div>

      {error && (
        <p className="me2-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
