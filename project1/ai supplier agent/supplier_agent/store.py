"""SQLite persistence (standard library). One connection guarded by a lock."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE,
    event_id TEXT,
    thread_id TEXT,
    received_at TEXT,
    from_addr TEXT,
    from_name TEXT,
    subject TEXT,
    outcome TEXT,
    headline TEXT,
    human_status TEXT,
    llm_mode TEXT,
    input_tokens INTEGER DEFAULT 0,
    cached_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0,
    estimated INTEGER DEFAULT 0,
    email_json TEXT,
    result_json TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_thread ON runs(thread_id);
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    thread_id TEXT,
    to_addr TEXT,
    subject TEXT,
    body TEXT,
    sent_by TEXT,
    sent_at TEXT
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    rating TEXT,
    note TEXT,
    created_at TEXT
);
"""

SUMMARY_COLUMNS = (
    "id, message_id, thread_id, received_at, from_addr, from_name, subject, outcome, headline, human_status, "
    "llm_mode, input_tokens, cached_tokens, output_tokens, cost_usd, estimated, updated_at"
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    # ------------------------------------------------------------- helpers
    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def _write(self, sql: str, params: tuple = ()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return int(cur.lastrowid or 0)

    # ---------------------------------------------------------------- runs
    def has_message(self, message_id: str) -> bool:
        return bool(self._query("SELECT 1 FROM runs WHERE message_id = ?", (message_id,)))

    def save_run(self, run: dict, run_id: int | None = None) -> int:
        usage = run.get("usage") or {}
        email = run.get("email") or {}
        values = (
            email.get("message_id"),
            email.get("event_id"),
            email.get("thread_id"),
            run.get("received_at") or now_iso(),
            email.get("from_addr"),
            email.get("from_name"),
            email.get("subject"),
            run.get("outcome"),
            run.get("headline"),
            run.get("human_status"),
            run.get("llm_mode"),
            int(usage.get("input_tokens", 0)),
            int(usage.get("cached_tokens", 0)),
            int(usage.get("output_tokens", 0)),
            float(usage.get("cost_usd", 0.0)),
            1 if usage.get("estimated") else 0,
            json.dumps(email, ensure_ascii=False),
            json.dumps(run, ensure_ascii=False, default=str),
            now_iso(),
        )
        cols = ("message_id, event_id, thread_id, received_at, from_addr, from_name, subject, outcome, headline, "
                "human_status, llm_mode, input_tokens, cached_tokens, output_tokens, cost_usd, estimated, "
                "email_json, result_json, updated_at")
        if run_id:
            assignments = ", ".join(f"{c.strip()} = ?" for c in cols.split(","))
            self._write(f"UPDATE runs SET {assignments} WHERE id = ?", values + (run_id,))
            return run_id
        placeholders = ", ".join("?" for _ in values)
        return self._write(f"INSERT INTO runs ({cols}) VALUES ({placeholders})", values)

    def update_run_fields(self, run_id: int, **fields) -> None:
        if not fields:
            return
        fields["updated_at"] = now_iso()
        assignments = ", ".join(f"{k} = ?" for k in fields)
        self._write(f"UPDATE runs SET {assignments} WHERE id = ?", tuple(fields.values()) + (run_id,))

    def update_run_result(self, run_id: int, result: dict) -> None:
        self.update_run_fields(run_id, result_json=json.dumps(result, ensure_ascii=False, default=str),
                               human_status=result.get("human_status"))

    def get_run(self, run_id: int) -> dict | None:
        rows = self._query("SELECT * FROM runs WHERE id = ?", (run_id,))
        if not rows:
            return None
        row = dict(rows[0])
        row["email"] = json.loads(row.pop("email_json") or "{}")
        row["result"] = json.loads(row.pop("result_json") or "{}")
        return row

    def list_runs(self, limit: int = 300) -> list[dict]:
        rows = self._query(f"SELECT {SUMMARY_COLUMNS} FROM runs ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    def thread_history(self, thread_id: str, before_message_id: str | None = None, limit: int = 6) -> list[dict]:
        items: list[dict] = []
        for r in self._query(
            "SELECT id, received_at, from_name, from_addr, subject, email_json FROM runs WHERE thread_id = ?",
            (thread_id,),
        ):
            email = json.loads(r["email_json"] or "{}")
            if before_message_id and email.get("message_id") == before_message_id:
                continue
            items.append({"direction": "inbound", "at": r["received_at"], "from": r["from_name"] or r["from_addr"],
                          "subject": r["subject"], "body": (email.get("text") or "")[:800]})
        for r in self._query("SELECT * FROM outbox WHERE thread_id = ?", (thread_id,)):
            items.append({"direction": "outbound", "at": r["sent_at"], "from": f"us ({r['sent_by']})",
                          "subject": r["subject"], "body": (r["body"] or "")[:800]})
        items.sort(key=lambda x: x["at"] or "")
        return items[-limit:]

    # -------------------------------------------------------------- outbox
    def add_outbox(self, run_id: int, thread_id: str, to_addr: str, subject: str, body: str, sent_by: str) -> int:
        return self._write(
            "INSERT INTO outbox (run_id, thread_id, to_addr, subject, body, sent_by, sent_at) VALUES (?,?,?,?,?,?,?)",
            (run_id, thread_id, to_addr, subject, body, sent_by, now_iso()),
        )

    def list_outbox(self, limit: int = 100) -> list[dict]:
        return [dict(r) for r in self._query("SELECT * FROM outbox ORDER BY id DESC LIMIT ?", (limit,))]

    def agent_replies_in_thread(self, thread_id: str, hours: int = 24) -> int:
        since = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
        rows = self._query(
            "SELECT COUNT(*) AS n FROM outbox WHERE thread_id = ? AND sent_by = 'agent' AND sent_at >= ?",
            (thread_id, since),
        )
        return int(rows[0]["n"]) if rows else 0

    # --------------------------------------------------------------- spend
    def spend_today(self) -> dict:
        midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
        rows = self._query(
            "SELECT COALESCE(SUM(cost_usd),0) AS cost, COALESCE(SUM(input_tokens),0) AS inp, "
            "COALESCE(SUM(cached_tokens),0) AS cached, COALESCE(SUM(output_tokens),0) AS outp, COUNT(*) AS runs "
            "FROM runs WHERE received_at >= ?",
            (midnight,),
        )
        r = rows[0]
        return {"cost_usd": float(r["cost"]), "input_tokens": int(r["inp"]), "cached_tokens": int(r["cached"]),
                "output_tokens": int(r["outp"]), "runs": int(r["runs"])}

    # ------------------------------------------------------------ settings
    def get_settings(self) -> dict:
        out = {}
        for r in self._query("SELECT key, value FROM settings"):
            try:
                out[r["key"]] = json.loads(r["value"])
            except json.JSONDecodeError:
                out[r["key"]] = r["value"]
        return out

    def set_settings(self, values: dict) -> None:
        with self._lock:
            for key, value in values.items():
                self._conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                                   (key, json.dumps(value)))
            self._conn.commit()

    # ------------------------------------------------------------ feedback
    def add_feedback(self, run_id: int, rating: str, note: str) -> int:
        return self._write("INSERT INTO feedback (run_id, rating, note, created_at) VALUES (?,?,?,?)",
                           (run_id, rating, note, now_iso()))

    def feedback_for(self, run_id: int) -> list[dict]:
        return [dict(r) for r in self._query("SELECT * FROM feedback WHERE run_id = ? ORDER BY id", (run_id,))]

    # --------------------------------------------------------------- reset
    def reset(self) -> None:
        with self._lock:
            self._conn.executescript(
                "DELETE FROM runs; DELETE FROM outbox; DELETE FROM feedback; "
                "DELETE FROM sqlite_sequence WHERE name IN ('runs', 'outbox', 'feedback');"  # ids restart at 1
            )
            self._conn.commit()
