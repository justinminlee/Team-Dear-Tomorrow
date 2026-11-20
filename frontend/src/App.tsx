
import { useState } from "react";
import LoginPage from "./components/LoginPage";
import SignUpPage from "./components/SignUpPage";
import LandingPage from "./components/LandingPage";

type Page = "login" | "signup" | "landing";

export default function App() {
  const [page, setPage] = useState<Page>("login");

  // 1. SIGN UP PAGE
  if (page === "signup") {
    return (
      <SignUpPage
        onLogin={() => setPage("login")}
        onSuccess={() => setPage("login")}
      />
    );
  }

  // 2. LOGIN PAGE
  if (page === "login") {
    return (
      <LoginPage
        onSignUp={() => setPage("signup")}
        onLogin={async (email, password) => {
          const response = await fetch(
            `${import.meta.env.VITE_API_URL}/auth/login`,
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
            throw new Error("Invalid email or password");
          }

          // Login successful
          setPage("landing");
        }}
      />
    );
  }

  // 3. LANDING PAGE
  return (
    <LandingPage
      onGetStarted={() => {
        console.log("Get Started clicked");
      }}
    />
  );
}
