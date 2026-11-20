
import { useState } from "react";

import WelcomePage from "./components/WelcomePage";
import LoginPage from "./components/LoginPage";
import SignUpPage from "./components/SignUpPage";
import QuestionnairePage, {
  type Question,
} from "./components/QuestionnairePage";

type Page =
  | "welcome"
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
  const [page, setPage] = useState<Page>("welcome");

  // 1. WELCOME
  if (page === "welcome") {
    return (
      <WelcomePage
        onStartQuestionnaire={() => setPage("login")}
      />
    );
  }

  // SIGN UP PAGE
  if (page === "signup") {
    return (
      <SignUpPage
        onLogin={() => setPage("login")}
        onSuccess={() => setPage("questionnaire")}
      />
    );
  }

  // 3. LOGIN
  if (page === "login") {
    return (
      <LoginPage
        onSignUp={() => setPage("signup")}
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
        minHeight: "100vh",
        background: "#0b0b0d",
        color: "#f2ede6",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        textAlign: "center",
        gap: "20px",
        padding: "24px",
      }}
    >
      <h1>You're ready to meet Tomorrow.</h1>

      <p>
        Questionnaire complete. Your answers
        have not been saved in this demo.
      </p>

      <button
        onClick={() => setPage("welcome")}
        style={{
          background: "#f5bf64",
          color: "#17100a",
          border: "none",
          borderRadius: "30px",
          padding: "14px 28px",
          cursor: "pointer",
        }}
      >
        Back to Welcome
      </button>
    </main>
  );
}
