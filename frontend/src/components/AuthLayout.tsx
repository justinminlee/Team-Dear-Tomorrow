import type { ReactNode } from "react";
import "./LoginPage.css";

type AuthLayoutProps = {
  /** Clicking the Me² logo returns to the landing page. */
  onHome?: () => void;
  children: ReactNode;
};

/** Shared page frame for Login and Sign up, matching the Me² landing page. */
export default function AuthLayout({ onHome, children }: AuthLayoutProps) {
  return (
    <main className="dt-login">
      <header className="dt-auth-header">
        <button
          type="button"
          className="dt-auth-logo"
          onClick={onHome}
          disabled={!onHome}
          aria-label="Me² home"
        >
          Me²
        </button>
        <div className="dt-auth-note">A CONVERSATION ACROSS TIME</div>
      </header>

      <div className="dt-login-content">{children}</div>

      <footer className="dt-auth-footer">
        <span>© Me² AI</span>
        <span>Imagine your future. Hear your possibilities.</span>
      </footer>
    </main>
  );
}
