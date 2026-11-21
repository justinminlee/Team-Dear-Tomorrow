
import { useCallback, useEffect, useRef, useState } from "react";

import Me2LandingPage from "./components/Me2LandingPage";
import LoginPage from "./components/LoginPage";
import SignUpPage from "./components/SignUpPage";
import QuestionnairePage, { type Answer } from "./components/QuestionnairePage";
import ConnectingPage from "./components/ConnectingPage";
import FutureCallPage from "./components/FutureCallPage";
import CallEndPage from "./components/CallEndPage";
import { useFutureCall } from "./call/useFutureCall";
import { callApi } from "./api/call";
import type { CallSnapshot } from "./call/futureCall";
import { ApiError, authApi } from "./api/auth";
import { questionnaireApi } from "./api/questionnaire";

type Page =
  | "landing"
  | "login"
  | "signup"
  | "questionnaire"
  | "complete"
  | "connecting"
  | "call"
  | "ended";

/** The line under the particle ring during a call. */
function callCaption({ phase, caption, muted }: CallSnapshot): string {
  if (phase === "speaking") return caption;
  if (muted) return "You're muted. Unmute to talk to your future self.";
  if (phase === "thinking") return "…";
  if (phase === "hearing") return "Listening…";
  if (phase === "listening") return caption || "Your turn. Speak whenever you're ready.";
  return "";
}

// How long "Your future self is calling." shows before the call screen opens.
const CONNECTED_PAUSE_MS = 1200;

export default function App() {
  const [page, setPage] = useState<Page>("landing");
  const [callSeconds, setCallSeconds] = useState(0);
  const call = useFutureCall(useCallback(() => setPage("login"), []));
  const connectTimer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(connectTimer.current), []);

  // Start from a click: the browser only allows call audio after a user gesture.
  // Cloned voices the future self can speak with (TJ, Peter, Indian), chosen before the call.
  const [voices, setVoices] = useState<string[]>([]);
  const [voice, setVoice] = useState("");
  useEffect(() => {
    callApi
      .voices()
      .then((res) => {
        setVoices(res.voices);
        setVoice((current) => current || res.default || "");
      })
      .catch(() => undefined); // no list: the call still works with the server's default voice
  }, []);

  const startCall = () => {
    void call.start(voice || undefined);
    setPage("connecting");
  };

  const { begin } = call;
  const handleConnected = useCallback(() => {
    connectTimer.current = window.setTimeout(() => {
      setPage("call");
      begin();
    }, CONNECTED_PAUSE_MS);
  }, [begin]);

  const leaveConnecting = () => {
    window.clearTimeout(connectTimer.current);
    call.end();
    setPage("complete");
  };

  const hangUp = () => {
    setCallSeconds(call.end());
    setPage("ended");
  };

  // If the session has expired, send the user back to log in.
  const handleApiError = useCallback((err: unknown): never => {
    if (err instanceof ApiError && err.status === 401) {
      setPage("login");
      throw new Error("Your session has expired. Please log in again.");
    }
    throw err;
  }, []);

  // useCallback keeps these stable so the questionnaire doesn't reload on every render.
  const loadQuestions = useCallback(() => questionnaireApi.questions(), []);
  const loadAnswers = useCallback(
    () => questionnaireApi.myAnswers().catch(handleApiError),
    [handleApiError]
  );
  const saveAnswers = useCallback(
    async (answers: Record<string, Answer>, spokenIds: string[]) => {
      await questionnaireApi.save(answers).catch(handleApiError);
      // Spoken answers also teach the future self how the user talks. The answers are
      // already saved at this point, so a problem here must not block the questionnaire.
      if (spokenIds.length > 0) {
        await questionnaireApi.saveVoiceSamples(spokenIds).catch((err) => {
          console.warn("Could not queue spoken answers for style learning:", err);
        });
      }
    },
    [handleApiError]
  );
  const transcribe = useCallback(
    (audio: Blob) => questionnaireApi.transcribe(audio).catch(handleApiError),
    [handleApiError]
  );

  // 1. LANDING
  if (page === "landing") {
    return <Me2LandingPage onLogin={() => setPage("login")} />;
  }

  // SIGN UP PAGE
  if (page === "signup") {
    return (
      <SignUpPage
        onLogin={() => setPage("login")}
        onSuccess={() => setPage("questionnaire")}
        onHome={() => setPage("landing")}
      />
    );
  }

  // 3. LOGIN
  if (page === "login") {
    return (
      <LoginPage
        onSignUp={() => setPage("signup")}
        onHome={() => setPage("landing")}
        onLogin={async (email, password) => {
          await authApi.login(email, password);

          // Successful login opens Questionnaire.
          setPage("questionnaire");
        }}
      />
    );
  }

  // 4. QUESTIONNAIRE
  if (page === "questionnaire") {
    return (
      <QuestionnairePage
        loadQuestions={loadQuestions}
        loadAnswers={loadAnswers}
        saveAnswers={saveAnswers}
        transcribe={transcribe}
        onBack={() => setPage("login")}
        onComplete={() => setPage("complete")}
      />
    );
  }

  // 6. CONNECTING TO THE FUTURE SELF
  if (page === "connecting") {
    const { phase, error } = call.snapshot;
    return (
      <ConnectingPage
        connected={phase === "ready"}
        onConnected={handleConnected}
        error={phase === "failed" ? error : undefined}
        onCancel={leaveConnecting}
      />
    );
  }

  // 7. IN CALL
  if (page === "call") {
    return (
      <FutureCallPage
        connected={call.snapshot.phase !== "ended"}
        aiAudioLevel={call.level}
        muted={call.snapshot.muted}
        onToggleMute={() => call.setMuted(!call.snapshot.muted)}
        onEndCall={hangUp}
        caption={callCaption(call.snapshot)}
      />
    );
  }

  // 8. CALL ENDED
  if (page === "ended") {
    return <CallEndPage onBackHome={() => setPage("landing")} durationSeconds={callSeconds} />;
  }

  // 5. COMPLETION SCREEN
  return (
    <main
      style={{
        minHeight: "100svh",
        background:
          "radial-gradient(ellipse 50% 45% at 50% 46%, #1b1b1d 0%, #111214 75%)",
        color: "#f3efe8",
        fontFamily:
          'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        textAlign: "center",
        padding: "24px",
      }}
    >
      <p
        style={{
          color: "#b7a997",
          fontSize: "11px",
          letterSpacing: "3px",
          fontWeight: 650,
          textTransform: "uppercase",
          margin: "0 0 20px",
        }}
      >
        Questionnaire complete
      </p>

      <h1
        style={{
          fontSize: "clamp(32px, 5vw, 56px)",
          fontWeight: 560,
          letterSpacing: "-0.06em",
          lineHeight: 1.1,
          margin: 0,
        }}
      >
        You're ready to meet tomorrow.
      </h1>

      <p
        style={{
          color: "#a8a8aa",
          fontSize: "15px",
          lineHeight: 1.7,
          margin: "18px 0 36px",
        }}
      >
        Your answers have been saved. Your future self is ready to talk.
      </p>

      {voices.length > 1 && (
        <div style={{ margin: "0 0 28px" }}>
          <p
            id="voice-picker-label"
            style={{ color: "#a8a8aa", fontSize: "12px", letterSpacing: "1.5px", fontWeight: 650, margin: "0 0 12px" }}
          >
            CHOOSE YOUR FUTURE SELF'S VOICE
          </p>
          <div
            role="radiogroup"
            aria-labelledby="voice-picker-label"
            style={{ display: "flex", gap: "10px", justifyContent: "center", flexWrap: "wrap" }}
          >
            {voices.map((name) => {
              const selected = voice === name;
              return (
                <button
                  key={name}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => setVoice(name)}
                  style={{
                    background: selected ? "#2a2926" : "transparent",
                    color: selected ? "#f3efe8" : "#a8a8aa",
                    border: `1px solid ${selected ? "#d9c8ae" : "#444649"}`,
                    borderRadius: "999px",
                    padding: "10px 22px",
                    fontSize: "14px",
                    fontWeight: 650,
                    cursor: "pointer",
                  }}
                >
                  {name}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <button
        onClick={startCall}
        style={{
          background: "#efeae2",
          color: "#181a1c",
          border: "1px solid #e7e1d8",
          borderRadius: "999px",
          padding: "15px 40px",
          fontSize: "15px",
          fontWeight: 650,
          cursor: "pointer",
        }}
      >
        Call your future self <span aria-hidden="true">↗</span>
      </button>

      <p style={{ color: "#7e7f81", fontSize: "12px", margin: "16px 0 0" }}>
        You'll need your microphone. Best with headphones.
      </p>

      <button
        onClick={() => setPage("questionnaire")}
        style={{
          background: "transparent",
          color: "#a8a8aa",
          border: 0,
          marginTop: "28px",
          fontSize: "13px",
          textDecoration: "underline",
          textUnderlineOffset: "3px",
          cursor: "pointer",
        }}
      >
        Review my answers
      </button>
    </main>
  );
}
