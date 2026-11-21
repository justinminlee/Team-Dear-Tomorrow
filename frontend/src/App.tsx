
import { useState } from "react";

import Me2LandingPage from "./components/Me2LandingPage";
import LoginPage from "./components/LoginPage";
import SignUpPage from "./components/SignUpPage";
import QuestionnairePage, {
  type Question,
} from "./components/QuestionnairePage";

type Page =
  | "landing"
  | "login"
  | "signup"
  | "questionnaire"
  | "complete";

// TEMPORARY SAMPLE QUESTIONS
// Replace these with FastAPI questions later.
const demoQuestions: Question[] = [
  {
    id: 1,
    text: "What should Tomorrow call you?",
    type: "text",
    sectionId: "about",
    sectionTitle: "About You",
    sectionDescription: "Let's start with the present.",
    placeholder: "Your preferred name",
    required: true,
    sectionOrder: 1,
  },
  {
    id: 2,
    text: "What part of your future interests you most?",
    type: "single_choice",
    sectionId: "future",
    sectionTitle: "Your Future",
    sectionDescription:
      "Tell us what you'd like to explore.",
    required: true,
    sectionOrder: 2,
    options: [
      { value: "career", label: "Career" },
      { value: "relationships", label: "Relationships" },
      { value: "personal", label: "Personal Growth" },
      { value: "lifestyle", label: "Lifestyle" },
    ],
  },
  {
    id: 3,
    text: "What would you like to ask your future self?",
    type: "textarea",
    sectionId: "future",
    sectionTitle: "Your Future",
    placeholder: "Write your question...",
    sectionOrder: 2,
  },
];

// Keep this function outside App so its reference stays stable.
async function loadDemoQuestions(): Promise<Question[]> {
  return demoQuestions;
}

export default function App() {
  const [page, setPage] = useState<Page>("landing");

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
          const apiUrl = import.meta.env.VITE_API_URL;

          if (!apiUrl) {
            throw new Error(
              "Backend API URL is not configured."
            );
          }

          const response = await fetch(
            `${apiUrl}/auth/login`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              credentials: "include",
              body: JSON.stringify({
                email,
                password,
              }),
            }
          );

          if (!response.ok) {
            throw new Error(
              "Invalid email or password"
            );
          }

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
      loadQuestions={loadDemoQuestions}
      onBackToLogin={() => setPage("login")}
      onSubmit={() => setPage("complete")}
    />
  );
  }

  // 5. TEMPORARY COMPLETION SCREEN
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
        Your answers have not been saved in this demo.
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
