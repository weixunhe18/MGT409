import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth";
import "./Pages.css";
import "./Auth.css";

const MIN_PASSWORD = 8;

const EMPTY = {
  first_name: "",
  last_name: "",
  email: "",
  password: "",
  confirm_password: "",
};

export default function CreateAccount() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const update = (field: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  // Shown live so the shopper fixes it before submitting. The server checks
  // both rules again — this is a courtesy, not the safeguard.
  const tooShort = form.password.length > 0 && form.password.length < MIN_PASSWORD;
  const mismatch = form.confirm_password.length > 0 && form.password !== form.confirm_password;
  const complete = Object.values(form).every((v) => v.trim().length > 0);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (form.password !== form.confirm_password) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await register(form);
      navigate("/products");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="shell page auth">
      <p className="eyebrow">Create Account</p>
      <h1>Open an Account</h1>
      <p className="page__lede">
        Name, address of the electronic sort, and a word kept secret. We shall ask
        for nothing further.
      </p>

      <form className="auth__form" onSubmit={submit} noValidate>
        <div className="auth__row">
          <label>
            <span>First name</span>
            <input
              autoComplete="given-name"
              value={form.first_name}
              onChange={update("first_name")}
              required
            />
          </label>
          <label>
            <span>Last name</span>
            <input
              autoComplete="family-name"
              value={form.last_name}
              onChange={update("last_name")}
              required
            />
          </label>
        </div>

        <label>
          <span>Email</span>
          <input
            type="email"
            autoComplete="email"
            value={form.email}
            onChange={update("email")}
            required
          />
        </label>

        <label>
          <span>Password</span>
          <input
            type="password"
            autoComplete="new-password"
            value={form.password}
            onChange={update("password")}
            aria-invalid={tooShort}
            required
          />
          <small className={tooShort ? "auth__hint auth__hint--bad" : "auth__hint"}>
            At least {MIN_PASSWORD} characters.
          </small>
        </label>

        <label>
          <span>Confirm password</span>
          <input
            type="password"
            autoComplete="new-password"
            value={form.confirm_password}
            onChange={update("confirm_password")}
            aria-invalid={mismatch}
            required
          />
          {mismatch && <small className="auth__hint auth__hint--bad">Passwords do not match.</small>}
        </label>

        {error && (
          <p className="auth__error" role="alert">
            {error}
          </p>
        )}

        <button
          type="submit"
          className="btn btn--primary"
          disabled={busy || !complete || tooShort || mismatch}
        >
          {busy ? "Entering you in the ledger…" : "Create Account"}
        </button>
      </form>

      <p className="auth__switch">
        Already have an account? <Link to="/login">Log in</Link>.
      </p>
    </article>
  );
}
