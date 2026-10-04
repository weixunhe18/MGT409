import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { forgotPassword } from "../api";
import "./Pages.css";
import "./Auth.css";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const { message } = await forgotPassword(email);
      setSent(message);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="shell page auth">
      <p className="eyebrow">Reset Password</p>
      <h1>A Key Mislaid</h1>
      <p className="page__lede">
        It happens to the best of us; I once misplaced a whole colony&rsquo;s worth
        of correspondence. Give us your email and we shall send a fresh key.
      </p>

      {sent ? (
        <>
          {/* Worded the same whether or not the account exists, so this page
              cannot be used to discover who shops here. */}
          <p className="auth__notice">{sent}</p>
          <p className="auth__switch">
            Remembered it after all? <Link to="/login">Back to log in</Link>.
          </p>
        </>
      ) : (
        <form className="auth__form" onSubmit={submit} noValidate>
          <label>
            <span>Email</span>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>

          {error && (
            <p className="auth__error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="btn btn--primary" disabled={busy || !email}>
            {busy ? "Sending…" : "Send Reset Link"}
          </button>
        </form>
      )}
    </article>
  );
}
