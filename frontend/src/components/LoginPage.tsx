
import { useState, type SubmitEvent } from "react";
import "./LoginPage.css";

type LoginPageProps = {
  onLogin: (
    email: string,
    password: string
  ) => Promise<void>;
  onSignUp: () => void;
};

export default function LoginPage({
  onLogin,
  onSignUp,
}: LoginPageProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(
    event: SubmitEvent<HTMLFormElement>
  ) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      await onLogin(email.trim(), password);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Login failed. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="dt-login">
      {/* Background glow */}
      <div className="dt-login-glow dt-glow-top" />
      <div className="dt-login-glow dt-glow-bottom" />

      <div className="dt-login-content">
        {/* Brand */}
        <div className="dt-login-brand">
          dear <span>tomorrow.</span>
        </div>


        {/* Heading */}
        <header className="dt-login-header">
          <h1>Welcome Back</h1>
          <p>Continue your call to tomorrow.</p>
        </header>

        {/* Login form */}
        <form
          className="dt-login-card"
          onSubmit={handleSubmit}
        >
          {/* Email */}
          <label className="dt-field">
            <span className="dt-visually-hidden">
              Email address
            </span>
            <input
              type="email"
              placeholder="Email address"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>

          {/* Password */}
          <label className="dt-field">
            <span className="dt-visually-hidden">
              Password
            </span>

            <input
              type={showPassword ? "text" : "password"}
              placeholder="Password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />

            <button
              type="button"
              className="dt-show-password"
              onClick={() =>
                setShowPassword(!showPassword)
              }
              aria-label={
                showPassword
                  ? "Hide password"
                  : "Show password"
              }
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </label>

          {/* Remember me */}
          <div className="dt-login-options">
            <label className="dt-remember">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) =>
                  setRememberMe(e.target.checked)
                }
              />
              Remember me
            </label>
          </div>

          {/* Error message */}
          {error && (
            <p className="dt-login-error" role="alert">
              {error}
            </p>
          )}

          {/* Login button */}
          <button
            type="submit"
            className="dt-login-submit"
            disabled={loading}
          >
            {loading
              ? "Logging in..."
              : "Log in →"}
          </button>
        </form>

        {/* Sign up link */}
        <p className="dt-login-signup">
          New to Dear Tomorrow?{" "}
          <button
            type="button"
            onClick={onSignUp}
          >
            Create an account
          </button>
        </p>
      </div>
    </main>
  );
}
