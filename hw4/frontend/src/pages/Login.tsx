import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../api";
import { useAuth } from "../auth";
import "./Pages.css";
import "./Auth.css";

const MAX_ATTEMPTS = 5;

function formatClock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  // Set by the reset page so a shopper lands here with confirmation, not silence.
  const notice = (location.state as { notice?: string } | null)?.notice;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [attemptsLeft, setAttemptsLeft] = useState<number | null>(null);
  const [lockedUntil, setLockedUntil] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);

  const secondsLeft = lockedUntil ? Math.max(0, Math.ceil((lockedUntil - now) / 1000)) : 0;
  const locked = secondsLeft > 0;

  // Tick once a second while locked; release the lock when the clock runs out.
  useEffect(() => {
    if (!lockedUntil) return;
    const timer = window.setInterval(() => {
      const t = Date.now();
      setNow(t);
      if (t >= lockedUntil) {
        setLockedUntil(null);
        setAttemptsLeft(null);
        setError(null);
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [lockedUntil]);

  // The limit is per email, so a countdown shown for one address says nothing
  // about another. Clear it when the shopper changes the email field.
  function changeEmail(value: string) {
    setEmail(value);
    if (attemptsLeft !== null || lockedUntil) {
      setAttemptsLeft(null);
      setLockedUntil(null);
      setError(null);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (locked) return;
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      navigate("/products");
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : null;
      setError((err as Error).message);
      setPassword("");
      if (apiErr?.info.retry_after) {
        setNow(Date.now());
        setLockedUntil(Date.now() + apiErr.info.retry_after * 1000);
        setAttemptsLeft(0);
      } else if (apiErr?.info.attempts_remaining !== undefined) {
        setAttemptsLeft(apiErr.info.attempts_remaining);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="shell page auth">
      <p className="eyebrow">Log In</p>
      <h1>Return to Your Account</h1>
      <p className="page__lede">
        A returning customer ought to be recognized at the door. State your name
        &mdash; or rather, your address of the electronic sort.
      </p>

      {notice && !error && <p className="auth__notice">{notice}</p>}

      <form className="auth__form" onSubmit={submit} noValidate>
        <label>
          <span>Email</span>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => changeEmail(e.target.value)}
            required
          />
        </label>

        <label>
          <span className="auth__label-row">
            Password
            <Link to="/forgot-password" className="auth__forgot">
              Forgot password?
            </Link>
          </span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={locked}
            required
          />
        </label>

        {locked ? (
          <div className="auth__error auth__lock" role="alert">
            <strong>Locked for {formatClock(secondsLeft)}</strong>
            <span>
              Five wrong passwords in a row. You can try again when the clock runs
              out, or <Link to="/forgot-password">reset your password</Link> now.
            </span>
          </div>
        ) : (
          error && (
            <div className="auth__error" role="alert">
              {error}
              {attemptsLeft !== null && attemptsLeft > 0 && (
                <AttemptMeter left={attemptsLeft} />
              )}
            </div>
          )
        )}

        <button
          type="submit"
          className="btn btn--primary"
          disabled={busy || locked || !email || !password}
        >
          {busy ? "Checking the ledger…" : locked ? `Try again in ${formatClock(secondsLeft)}` : "Log In"}
        </button>
      </form>

      <p className="auth__switch">
        New to the shop? <Link to="/create-account">Open an account</Link>.
      </p>
    </article>
  );
}

/** Pips for the attempts left, so the countdown is visible at a glance. */
function AttemptMeter({ left }: { left: number }) {
  return (
    <span className="attempts">
      <span className="attempts__pips" aria-hidden="true">
        {Array.from({ length: MAX_ATTEMPTS }, (_, i) => (
          <span key={i} className={i < left ? "pip pip--left" : "pip"} />
        ))}
      </span>
      <strong>
        {left} {left === 1 ? "attempt" : "attempts"} left
      </strong>{" "}
      before a 15-minute lockout.
    </span>
  );
}
