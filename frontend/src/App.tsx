
import { useCallback, useState } from "react";

import Me2LandingPage from "./components/Me2LandingPage";
import LoginPage from "./components/LoginPage";
import SignUpPage from "./components/SignUpPage";
import QuestionnairePage, { type Answer } from "./components/QuestionnairePage";
import { ApiError, authApi } from "./api/auth";
import { questionnaireApi } from "./api/questionnaire";

type Page =
  | "landing"
  | "login"
  | "signup"
  | "questionnaire"
  | "complete";

export default function App() {
  const [page, setPage] = useState<Page>("landing");

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
    async (answers: Record<string, Answer>) => {
      await questionnaireApi.save(answers).catch(handleApiError);
    },
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
        onBack={() => setPage("login")}
        onComplete={() => setPage("complete")}
      />
    );
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
        Your answers have been saved. You can come back and update them anytime.
      </p>

      <button
        onClick={() => setPage("landing")}
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
        Back to home
      </button>
    </main>
  );
}
