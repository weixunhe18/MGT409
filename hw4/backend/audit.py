"""Append-only audit log of agent activity.

Written to `output/audit_trail.json` as **JSON Lines**: one complete JSON object
per line, appended with `open(..., "a")` and never rewritten. That is what makes
it genuinely append-only — a single JSON array would have to be re-serialised on
every write, so a crash mid-write could truncate the whole history, and two
concurrent writers could lose records.

Read it back with:

    import json
    rows = [json.loads(line) for line in open("output/audit_trail.json")]

What is deliberately **not** logged: passwords, password hashes, session tokens,
email addresses, and reset links. A shopper is identified by `user_id` only, and
their message is truncated. An audit trail that leaks what it audits is worse
than none.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import AUDIT_PATH

MAX_TEXT = 160


def short(value: Any, limit: int = MAX_TEXT) -> Any:
    """Trim long strings so one odd turn cannot bloat the log."""
    if isinstance(value, str):
        collapsed = " ".join(value.split())
        return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"
    if isinstance(value, dict):
        return {k: short(v, 60) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [short(v, 60) for v in value[:5]]
    return value


def append(record: dict[str, Any]) -> None:
    """Append one record. Never raises — auditing must not break the shop."""
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), **record},
            ensure_ascii=False,
        )
        # Opened per write in append mode: the OS keeps the offset at EOF, so an
        # existing file is extended rather than replaced, across restarts.
        with open(AUDIT_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:  # noqa: BLE001 - logging must never take the request down
        pass
