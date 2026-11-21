
import { useState, type FormEvent } from "react";
import AuthLayout from "./AuthLayout";
import "./SignUpPage.css";

type SignUpPageProps = {
  onLogin: () => void;
  onSuccess: () => void;
  onHome?: () => void;
};

export default function SignUpPage({
  onLogin,
  onSuccess,
  onHome,
}: SignUpPageProps) {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const requirements = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    number: /[0-9]/.test(password),
    special: /[^A-Za-z0-9]/.test(password),
  };

  const validPassword = Object.values(requirements).every(Boolean);
  const passwordsMatch =
    password.length > 0 && password === confirmPassword;

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();
    setError("");

    if (!username.trim()) {
      setError("Please enter a username.");
      return;
    }

    if (!validPassword) {
      setError("Your password doesn't meet the requirements.");
      return;
    }

    if (!passwordsMatch) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      const apiUrl = import.meta.env.VITE_API_URL;

      if (!apiUrl) {
        throw new Error("API URL is not configured.");
      }

      const response = await fetch(
        `${apiUrl}/auth/register`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            username: username.trim(),
            email: email.trim().toLowerCase(),
            password,
          }),
        }
      );

      if (!response.ok) {
        const data = await response.json().catch(() => null);

        throw new Error(
          typeof data?.detail === "string"
            ? data.detail
            : response.status === 409
              ? "This email is already registered."
              : "Could not create your account."
        );
      }

      setPassword("");
      setConfirmPassword("");
      onSuccess();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout onHome={onHome}>
        <header className="dt-login-header">
          <p className="dt-login-eyebrow">Begin here</p>
          <h1>Create your account</h1>
          <p className="dt-login-sub">Your future is just one conversation away.</p>
        </header>

        <form
          className="dt-login-card"
          onSubmit={handleSubmit}
        >
          {/* USERNAME */}
          <label className="dt-field">
            <span className="dt-visually-hidden">
              Username
            </span>
            <input
              type="text"
              placeholder="Username"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              maxLength={255}
              required
            />
          </label>

          {/* EMAIL */}
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
              maxLength={255}
              required
            />
          </label>

          {/* PASSWORD */}
          <label className="dt-field">
            <span className="dt-visually-hidden">
              Password
            </span>
            <input
              type={showPassword ? "text" : "password"}
              placeholder="Create password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />

            <button
              type="button"
              className="dt-show-password"
              onClick={() => setShowPassword(!showPassword)}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </label>

          {/* PASSWORD REQUIREMENTS */}
          <div className="dt-password-requirements">
            <PasswordRule
              valid={requirements.length}
              label="At least 8 characters"
            />
            <PasswordRule
              valid={requirements.uppercase}
              label="One uppercase letter"
            />
            <PasswordRule
              valid={requirements.number}
              label="One number"
            />
            <PasswordRule
              valid={requirements.special}
              label="One special character"
            />
          </div>

          {/* CONFIRM PASSWORD */}
          <label className="dt-field">
            <span className="dt-visually-hidden">
              Confirm password
            </span>
            <input
              type={showPassword ? "text" : "password"}
              placeholder="Confirm password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) =>
                setConfirmPassword(e.target.value)
              }
              required
            />
          </label>

          {confirmPassword && !passwordsMatch && (
            <p className="dt-login-error">
              Passwords do not match.
            </p>
          )}

          {error && (
            <p className="dt-login-error" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            className="dt-login-submit"
            disabled={
              loading ||
              !username.trim() ||
              !validPassword ||
              !passwordsMatch
            }
          >
            {loading
              ? "Creating account..."
              : "Create account →"}
          </button>
        </form>

        <p className="dt-login-signup">
          Already have an account?{" "}
          <button type="button" onClick={onLogin}>
            Log in
          </button>
        </p>
    </AuthLayout>
  );
}

function PasswordRule({
  valid,
  label,
}: {
  valid: boolean;
  label: string;
}) {
  return (
    <div
      className={`dt-password-rule ${
        valid ? "valid" : ""
      }`}
    >
      <span aria-hidden="true">
        {valid ? "✓" : "○"}
      </span>
      <span>{label}</span>
    </div>
  );
}
