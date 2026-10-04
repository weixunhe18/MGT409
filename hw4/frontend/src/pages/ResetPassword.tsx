import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { resetPassword } from "../api";
import { useAuth } from "../auth";
import "./Pages.css";
import "./Auth.css";

const MIN_PASSWORD = 8;

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const { logout } = useAuth();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const tooShort = password.length > 0 && password.length < MIN_PASSWORD;
  const mismatch = confirm.length > 0 && password !== confirm;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const { message } = await resetPassword(token, password, confirm);
      // The server voids every older session; mirror that in the nav.
      await logout().catch(() => undefined);
      navigate("/login", { state: { notice: message } });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <article className="shell page auth">
        <p className="eyebrow">Reset Password</p>
        <h1>No Key Presented</h1>
        <p className="auth__error">
          This page needs the link from your reset email. Request a new one below.
        </p>
        <div className="page__actions">
          <Link to="/forgot-password" className="btn btn--primary">
            Request a Reset Link
          </Link>
        </div>
      </article>
    );
  }

  return (
    <article className="shell page auth">
      <p className="eyebrow">Reset Password</p>
      <h1>Choose a New Password</h1>
      <p className="page__lede">
        The old one is forgotten; let the new one be harder to forget and harder
        still to guess.
      </p>

      <form className="auth__form" onSubmit={submit} noValidate>
        <label>
          <span>New password</span>
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-invalid={tooShort}
            required
          />
          <small className={tooShort ? "auth__hint auth__hint--bad" : "auth__hint"}>
            At least {MIN_PASSWORD} characters.
          </small>
        </label>

        <label>
          <span>Confirm new password</span>
          <input
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            aria-invalid={mismatch}
            required
          />
          {mismatch && <small className="auth__hint auth__hint--bad">Passwords do not match.</small>}
        </label>

        {error && (
          <div className="auth__error" role="alert">
            {error}{" "}
            <Link to="/forgot-password">Request a new link</Link>.
          </div>
        )}

        <button
          type="submit"
          className="btn btn--primary"
          disabled={busy || !password || !confirm || tooShort || mismatch}
        >
          {busy ? "Changing the lock…" : "Set New Password"}
        </button>
      </form>
    </article>
  );
}
