"""AgentMail-compatible webhooks (Svix signing scheme) and payload normalization.

AgentMail delivers `message.received` events signed with Svix headers:
    svix-id, svix-timestamp, svix-signature: "v1,<base64 HMAC-SHA256>"
signed content = f"{svix_id}.{svix_timestamp}.{raw_body}", key = base64-decoded part after "whsec_".
We implement the same scheme so the mock inbox and a future real AgentMail inbox hit the
same, verified code path. Unsigned or stale requests are rejected before any work happens.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
import uuid

from .guardrails import parse_address

TOLERANCE_SECONDS = 300


def _key(secret: str) -> bytes:
    if secret.startswith("whsec_"):
        try:
            return base64.b64decode(secret[len("whsec_"):])
        except (binascii.Error, ValueError):
            pass
    return secret.encode("utf-8")


def sign(secret: str, msg_id: str, timestamp: int | str, body: bytes) -> str:
    to_sign = f"{msg_id}.{timestamp}.".encode("utf-8") + body
    digest = hmac.new(_key(secret), to_sign, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode("ascii")


def signed_headers(secret: str, body: bytes) -> dict[str, str]:
    msg_id = "msg_" + uuid.uuid4().hex
    ts = int(time.time())
    return {
        "Content-Type": "application/json",
        "svix-id": msg_id,
        "svix-timestamp": str(ts),
        "svix-signature": sign(secret, msg_id, ts, body),
    }


def verify(secret: str, headers, body: bytes, now: float | None = None) -> tuple[bool, str]:
    """headers: any mapping with case-insensitive .get (http.server headers) or a plain dict."""

    def get(name: str) -> str:
        value = headers.get(name) or headers.get(name.title()) or headers.get(name.replace("svix", "webhook"))
        return str(value or "").strip()

    msg_id, ts_raw, sig_header = get("svix-id"), get("svix-timestamp"), get("svix-signature")
    if not (msg_id and ts_raw and sig_header):
        return False, "missing svix signature headers"
    try:
        ts = int(ts_raw)
    except ValueError:
        return False, "bad timestamp"
    now = time.time() if now is None else now
    if abs(now - ts) > TOLERANCE_SECONDS:
        return False, "timestamp outside 5-minute tolerance (possible replay)"
    expected = sign(secret, msg_id, ts, body).split(",", 1)[1]
    for part in sig_header.split():
        version, _, sig = part.partition(",")
        if version == "v1" and hmac.compare_digest(sig, expected):
            return True, "signature verified"
    return False, "signature mismatch"


def normalize_event(event: dict) -> dict:
    """Flatten an AgentMail `message.received` event into the fields the pipeline uses."""
    msg = event.get("message") or {}
    from_raw = msg.get("from") or ""
    if isinstance(from_raw, list):
        from_raw = from_raw[0] if from_raw else ""
    from_name, from_addr = parse_address(str(from_raw))

    def as_list(value) -> list[str]:
        if not value:
            return []
        return [str(v) for v in value] if isinstance(value, list) else [str(value)]

    text = msg.get("extracted_text") or msg.get("text") or ""
    message_id = str(msg.get("message_id") or event.get("event_id") or ("<" + uuid.uuid4().hex + "@local>"))
    return {
        "event_id": str(event.get("event_id") or ""),
        "event_type": str(event.get("event_type") or ""),
        "inbox_id": str(msg.get("inbox_id") or ""),
        "message_id": message_id,
        "thread_id": str(msg.get("thread_id") or message_id),
        "from_raw": str(from_raw),
        "from_name": from_name,
        "from_addr": from_addr,
        "to": as_list(msg.get("to")),
        "cc": as_list(msg.get("cc")),
        "subject": str(msg.get("subject") or "(no subject)"),
        "text": str(text),
        "html": msg.get("html") or msg.get("extracted_html") or None,
        "attachments": msg.get("attachments") or [],
        "headers": msg.get("headers") or {},
        "in_reply_to": msg.get("in_reply_to"),
        "timestamp": str(msg.get("timestamp") or ""),
        "agent_armor": msg.get("agent_armor"),
        # Set only by the Gmail connector: where the email came from and its DKIM/DMARC verdict.
        "source": str(msg.get("source") or "webhook"),
        "auth": msg.get("auth"),
        "demo": event.get("_demo") or {},
    }


def make_event(*, from_header: str, subject: str, text: str, html: str | None = None,
               thread_id: str | None = None, inbox_id: str = "") -> dict:
    """Build a `message.received` event (used by the 'compose a test email' panel)."""
    mid = f"<compose.{uuid.uuid4().hex[:12]}@local.test>"
    return {
        "type": "event",
        "event_type": "message.received",
        "event_id": "evt_" + uuid.uuid4().hex[:16],
        "message": {
            "inbox_id": inbox_id,
            "thread_id": thread_id or ("thr_" + uuid.uuid4().hex[:10]),
            "message_id": mid,
            "labels": ["received"],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "from": from_header,
            "to": [inbox_id] if inbox_id else [],
            "cc": [],
            "subject": subject,
            "text": text,
            "html": html or None,
            "attachments": [],
            "headers": {},
        },
    }


def dumps(event: dict) -> bytes:
    return json.dumps(event, ensure_ascii=False).encode("utf-8")
