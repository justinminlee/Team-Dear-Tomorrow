import { useEffect, useState } from "react";
import LoginPage from "./components/LoginPage";
import SignUpPage from "./components/SignUpPage";
import LandingPage from "./components/LandingPage";
import { authApi, type AuthUser } from "./api/auth";

type Page = "login" | "signup" | "landing";

export default function App() {
  const [page, setPage] = useState<Page>("login");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checking, setChecking] = useState(true);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    authApi.me().then(({ user }) => {
      if (active) { setUser(user); setPage("landing"); }
    }).catch(() => { /* No active session */ }).finally(() => {
      if (active) setChecking(false);
    });
    return () => { active = false; };
  }, []);

  if (checking) return <main className="dt-login"><div className="dt-login-content">Checking your session…</div></main>;

  if (page === "signup") return (
    <SignUpPage
      onLogin={() => setPage("login")}
      onSuccess={(message) => { setNotice(message); setPage("login"); }}
    />
  );
  if (page === "login" || !user) return (
    <>
      {notice && <p role="status" style={{ textAlign: "center", padding: 12 }}>{notice}</p>}
      <LoginPage
        onSignUp={() => { setNotice(""); setPage("signup"); }}
        onLogin={async (email, password) => {
          const data = await authApi.login(email, password);
          setUser(data.user);
          setNotice("");
          setPage("landing");
        }}
      />
    </>
  );
  return (
    <>
      <div style={{ position: "absolute", top: 16, right: 20, zIndex: 10, display: "flex", gap: 12, alignItems: "center" }}>
        <span>{user.username || user.email}</span>
        <button type="button" onClick={async () => {
          try { await authApi.logout(); setUser(null); setPage("login"); }
          catch (error) { window.alert(error instanceof Error ? error.message : "Logout failed"); }
        }}>Log out</button>
      </div>
      <LandingPage onGetStarted={() => { console.log("Get Started clicked"); }} />
    </>
  );
}
