"""Accounts, password hashing, sessions, login throttling, and password reset.

Passwords
---------
Stored only as PBKDF2-HMAC-SHA256 digests with a per-user random salt — never in
plain text, never reversible. Two formats are understood:

  pbkdf2_sha256$<salt>$<hex>               legacy seed rows, 120,000 iterations implied
  pbkdf2_sha256$<iterations>$<salt>$<hex>  everything we write, iterations recorded

New hashes use 600,000 iterations (OWASP's current figure for PBKDF2-SHA256).
Recording the count in the hash means it can be raised later without breaking
existing accounts; a legacy hash is upgraded the next time its owner logs in.

Sessions
--------
A signed JWT in an httpOnly cookie. Page JavaScript cannot read it, so injected
script cannot steal a session. The token carries only the user id. A password
reset invalidates every session issued before it.

Login throttling
----------------
Five failed attempts per email, then a 15-minute lockout. Counted for *every*
email, registered or not — if only real accounts showed a countdown, the counter
itself would reveal which emails have accounts.

Password reset
--------------
A single-use, 30-minute token. Only its SHA-256 is stored, so a database leak does
not hand out working reset links. The link is delivered out of band (see
`_deliver_reset_link`) and is never returned by the API — if it were, anyone could
reset anyone's password by asking for it.
"""

import hashlib
import hmac
import logging
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field, field_validator

from config import FRONTEND_URL, JWT_ALGORITHM, JWT_SECRET, JWT_TTL_HOURS
from db import get_connection

log = logging.getLogger("uvicorn.error")

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
LEGACY_ITERATIONS = 120_000  # what the shipped seed rows were hashed with
SALT_BYTES = 16
MIN_PASSWORD_LENGTH = 8
COOKIE_NAME = "cc_session"

MAX_FAILED_LOGINS = 5
LOCKOUT = timedelta(minutes=15)
RESET_TOKEN_TTL = timedelta(minutes=30)

INVALID_LOGIN = "Invalid email or password."

# Burned on unknown emails so a miss takes as long as a wrong password —
# otherwise response timing would reveal which emails have accounts.
_DUMMY_HASH = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


# --- Schema -------------------------------------------------------------------


def ensure_auth_tables() -> None:
    """Auth bookkeeping lives in its own tables; the shipped `users` columns are
    left exactly as they arrived."""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS login_throttle (
                email          TEXT PRIMARY KEY,
                failures       INTEGER NOT NULL,
                last_failed_at TEXT NOT NULL,
                locked_until   TEXT
            );
            CREATE TABLE IF NOT EXISTS password_resets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                token_hash  TEXT NOT NULL UNIQUE,
                created_at  TEXT NOT NULL,
                expires_at  TEXT NOT NULL,
                used_at     TEXT
            );
            """
        )


# --- Password hashing ---------------------------------------------------------


def _derive(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    ).hex()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(SALT_BYTES)
    return f"{ALGORITHM}${ITERATIONS}${salt}${_derive(password, salt, ITERATIONS)}"


def _parse(stored: str) -> tuple[int, str, str] | None:
    """Return (iterations, salt, digest), or None if the format is unrecognized."""
    parts = stored.split("$")
    if parts[0] != ALGORITHM:
        return None
    if len(parts) == 3:
        return LEGACY_ITERATIONS, parts[1], parts[2]
    if len(parts) == 4 and parts[1].isdigit():
        return int(parts[1]), parts[2], parts[3]
    return None


def verify_password(password: str, stored: str) -> bool:
    parsed = _parse(stored)
    if parsed is None:
        return False
    iterations, salt, digest = parsed
    # compare_digest runs in constant time, so a near-miss is not faster to reject.
    return hmac.compare_digest(_derive(password, salt, iterations), digest)


def needs_rehash(stored: str) -> bool:
    parsed = _parse(stored)
    return parsed is None or parsed[0] < ITERATIONS


def _burn_time(password: str) -> None:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_hex(8))
    verify_password(password, _DUMMY_HASH)


# --- Login throttling ---------------------------------------------------------


def _throttle_state(conn: sqlite3.Connection, email: str) -> tuple[int, datetime | None]:
    """Current (failures, locked_until) for an email, clearing anything stale.

    Failures older than the lockout window are forgotten, so five typos spread
    across a week never lock anyone out."""
    row = conn.execute("SELECT * FROM login_throttle WHERE email = ?", (email,)).fetchone()
    if row is None:
        return 0, None

    now = _now()
    locked_until = _parse_time(row["locked_until"])
    if locked_until and locked_until > now:
        return row["failures"], locked_until

    if locked_until or _parse_time(row["last_failed_at"]) < now - LOCKOUT:
        conn.execute("DELETE FROM login_throttle WHERE email = ?", (email,))
        return 0, None

    return row["failures"], None


def _record_failure(conn: sqlite3.Connection, email: str, failures: int) -> tuple[int, datetime | None]:
    failures += 1
    now = _now()
    locked_until = now + LOCKOUT if failures >= MAX_FAILED_LOGINS else None
    conn.execute(
        "INSERT INTO login_throttle (email, failures, last_failed_at, locked_until)"
        " VALUES (?, ?, ?, ?)"
        " ON CONFLICT(email) DO UPDATE SET failures = excluded.failures,"
        " last_failed_at = excluded.last_failed_at, locked_until = excluded.locked_until",
        (email, failures, now.isoformat(), locked_until.isoformat() if locked_until else None),
    )
    return failures, locked_until


def _locked_error(locked_until: datetime) -> HTTPException:
    seconds = max(1, int((locked_until - _now()).total_seconds()))
    minutes = -(-seconds // 60)  # ceiling
    return HTTPException(
        status_code=429,
        detail={
            "message": (
                f"Too many failed attempts. Try again in {minutes} "
                f"minute{'s' if minutes != 1 else ''}, or reset your password."
            ),
            "retry_after": seconds,
        },
        headers={"Retry-After": str(seconds)},
    )


# --- Sessions -----------------------------------------------------------------


def issue_token(user_id: int) -> str:
    now = _now()
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=JWT_TTL_HOURS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode(token: str | None) -> tuple[int, int] | None:
    """Return (user_id, issued_at_epoch) for a valid token, else None."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"]), int(payload["iat"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None


def _set_session(response: Response, user_id: int) -> None:
    response.set_cookie(
        COOKIE_NAME,
        issue_token(user_id),
        max_age=JWT_TTL_HOURS * 3600,
        httponly=True,  # invisible to page JavaScript
        samesite="lax",  # not sent on cross-site form posts
        secure=False,  # localhost is plain http; set True behind https
        path="/",
    )


# --- Users --------------------------------------------------------------------


def public_user(row: sqlite3.Row) -> dict[str, object]:
    """The only shape a user ever leaves the server in. No password_hash."""
    first = row["first_name"] or (row["name"] or "").split(" ")[0]
    last = row["last_name"] or ""
    return {
        "id": row["id"],
        "email": row["email"],
        "first_name": first,
        "last_name": last,
        "name": row["name"],
        # The agent uses this for "you've been with us since..."; it is the
        # shopper's own signup date, never anyone else's.
        "created_at": row["created_at"],
    }


def get_user(user_id: int) -> dict[str, object] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return public_user(row) if row else None


def current_user(token: str | None) -> dict[str, object] | None:
    decoded = _decode(token)
    if decoded is None:
        return None
    user_id, issued_at = decoded

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        last_reset = conn.execute(
            "SELECT MAX(used_at) AS t FROM password_resets WHERE user_id = ? AND used_at IS NOT NULL",
            (user_id,),
        ).fetchone()["t"]

    if row is None:
        return None
    # A reset logs the account out everywhere: any session issued before it is void.
    # Compared at whole-second precision, matching the JWT `iat` claim.
    if last_reset and issued_at < int(_parse_time(last_reset).timestamp()):
        return None
    return public_user(row)


# --- Password reset delivery --------------------------------------------------


def _deliver_reset_link(email: str, token: str) -> None:
    """DEV STAND-IN FOR EMAIL. There is no mail server, so the link is written to
    the backend log, which only someone with access to the server can read.
    Replace this one function with a real mail service (SES, Postmark, SendGrid)
    before deploying; nothing else needs to change."""
    link = f"{FRONTEND_URL}/reset-password?token={token}"
    log.warning("[DEV MAIL] To: %s | Reset your Campus Customs password: %s", email, link)


def _hash_token(token: str) -> str:
    # A plain SHA-256 is right here: the token is 256 random bits, so there is
    # nothing to brute-force, and the lookup must be by exact hash.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --- API ----------------------------------------------------------------------


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)
    confirm_password: str

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_names(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=256)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)
    confirm_password: str


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(body: RegisterRequest, response: Response) -> dict[str, object]:
    # Checked here as well as in the form: the browser is not a security boundary.
    if body.password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    email = body.email.strip().lower()
    full_name = f"{body.first_name} {body.last_name}"

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash, first_name, last_name)"
                " VALUES (?, ?, ?, ?, ?)",
                (full_name, email, hash_password(body.password), body.first_name, body.last_name),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # The UNIQUE constraint on email is the duplicate check — no race window.
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    _set_session(response, user_id)
    return get_user(user_id)


@router.post("/login")
def login(body: LoginRequest, response: Response) -> dict[str, object]:
    email = body.email.strip().lower()

    # Decide inside the transaction, raise after it: get_connection commits only on a
    # clean exit, and a failure must be recorded or the counter never moves.
    error: HTTPException | None = None
    user_row = None

    with get_connection() as conn:
        failures, locked_until = _throttle_state(conn, email)

        if locked_until:
            # Refuse before checking the password — otherwise the lock is decorative
            # and an attacker could keep guessing, just with an error attached.
            error = _locked_error(locked_until)
        else:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if row is None:
                _burn_time(body.password)
                ok = False
            else:
                ok = verify_password(body.password, row["password_hash"])

            if not ok:
                failures, locked_until = _record_failure(conn, email, failures)
                if locked_until:
                    error = _locked_error(locked_until)
                else:
                    error = HTTPException(
                        status_code=401,
                        detail={
                            "message": INVALID_LOGIN,
                            "attempts_remaining": MAX_FAILED_LOGINS - failures,
                        },
                    )
            else:
                conn.execute("DELETE FROM login_throttle WHERE email = ?", (email,))
                # Quietly lift old hashes to the current cost while we hold the plaintext.
                if needs_rehash(row["password_hash"]):
                    conn.execute(
                        "UPDATE users SET password_hash = ? WHERE id = ?",
                        (hash_password(body.password), row["id"]),
                    )
                user_row = row

    if error:
        raise error

    _set_session(response, user_row["id"])
    return public_user(user_row)


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(cc_session: str | None = Cookie(default=None)) -> dict[str, object]:
    user = current_user(cc_session)
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in.")
    return user


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest) -> dict[str, str]:
    email = body.email.strip().lower()
    token = None

    with get_connection() as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            now = _now()
            token = secrets.token_urlsafe(32)
            # Only the newest link works; asking again retires the old one. Retire by
            # *expiring* it, never by setting used_at: used_at means "a reset was
            # completed" and voids every session, so stamping it here would let
            # anyone log a stranger out by requesting two links for their email.
            conn.execute(
                "UPDATE password_resets SET expires_at = ?"
                " WHERE user_id = ? AND used_at IS NULL AND expires_at > ?",
                (now.isoformat(), row["id"], now.isoformat()),
            )
            conn.execute(
                "INSERT INTO password_resets (user_id, token_hash, created_at, expires_at)"
                " VALUES (?, ?, ?, ?)",
                (row["id"], _hash_token(token), now.isoformat(), (now + RESET_TOKEN_TTL).isoformat()),
            )

    if token:
        _deliver_reset_link(email, token)

    # Identical whether or not the account exists — this endpoint must not become a
    # way to test which emails are registered.
    minutes = int(RESET_TOKEN_TTL.total_seconds() // 60)
    return {
        "message": (
            "If an account exists for that email, a password reset link is on its way. "
            f"It works once and expires in {minutes} minutes."
        )
    }


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, response: Response) -> dict[str, str]:
    if body.password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    now = _now()
    valid = False

    with get_connection() as conn:
        reset = conn.execute(
            "SELECT * FROM password_resets WHERE token_hash = ?", (_hash_token(body.token),)
        ).fetchone()

        if reset and reset["used_at"] is None and _parse_time(reset["expires_at"]) > now:
            valid = True
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(body.password), reset["user_id"]),
            )
            conn.execute(
                "UPDATE password_resets SET used_at = ? WHERE id = ?", (now.isoformat(), reset["id"])
            )
            # A successful reset is also the way out of a lockout.
            email = conn.execute(
                "SELECT email FROM users WHERE id = ?", (reset["user_id"],)
            ).fetchone()["email"]
            conn.execute("DELETE FROM login_throttle WHERE email = ?", (email,))

    if not valid:
        raise HTTPException(
            status_code=400,
            detail="This reset link is invalid, already used, or expired.",
        )

    response.delete_cookie(COOKIE_NAME, path="/")
    return {"message": "Your password has been changed. Log in with the new one."}
