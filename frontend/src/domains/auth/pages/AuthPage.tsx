import { FormEvent, useState } from "react";
import { KeyRound, LogIn, UserPlus } from "lucide-react";
import { Spinner } from "../../../components/Spinner";

type AuthPageProps = {
  mode: "bootstrap" | "login" | "change-password";
  error: string | null;
  onBootstrap: (username: string, password: string, email: string) => Promise<void>;
  onLogin: (username: string, password: string) => Promise<void>;
  onChangePassword: (currentPassword: string, newPassword: string) => Promise<void>;
};

export function AuthPage({ mode, error, onBootstrap, onLogin, onChangePassword }: AuthPageProps) {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);
    setIsSubmitting(true);
    try {
      if (mode === "bootstrap") {
        await onBootstrap(username, password, email);
      } else if (mode === "change-password") {
        await onChangePassword(password, newPassword);
      } else {
        await onLogin(username, password);
      }
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  const title =
    mode === "bootstrap" ? "Create Owner" : mode === "change-password" ? "Change Password" : "Sign In";
  const ButtonIcon = mode === "bootstrap" ? UserPlus : mode === "change-password" ? KeyRound : LogIn;

  return (
    <main className="auth-screen">
      <form className="auth-panel" onSubmit={handleSubmit}>
        <div className="brand-lockup auth-brand">
          <span className="brand-mark">3P</span>
          <span>3D Print Pilot</span>
        </div>
        <h1>{title}</h1>
        {error || localError ? <p className="form-error">{localError ?? error}</p> : null}

        {mode !== "change-password" ? (
          <label className="field-label">
            Username
            <input autoComplete="username" onChange={(event) => setUsername(event.target.value)} value={username} />
          </label>
        ) : null}

        {mode === "bootstrap" ? (
          <label className="field-label">
            Email
            <input autoComplete="email" onChange={(event) => setEmail(event.target.value)} type="email" value={email} />
          </label>
        ) : null}

        <label className="field-label">
          {mode === "change-password" ? "Current password" : "Password"}
          <input
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            value={password}
          />
        </label>

        {mode === "change-password" ? (
          <label className="field-label">
            New password
            <input
              autoComplete="new-password"
              onChange={(event) => setNewPassword(event.target.value)}
              type="password"
              value={newPassword}
            />
          </label>
        ) : null}

        <button className="primary-action icon-action" disabled={isSubmitting} type="submit">
          {isSubmitting ? <Spinner size={15} /> : <ButtonIcon size={15} aria-hidden="true" />}
          <span>{title}</span>
        </button>
      </form>
    </main>
  );
}
