"""Gmail connector: IMAP polling in, SMTP replies out (standard library only).

Receiving is *pulled* (IMAP every MAILBOX_POLL_SECONDS), so it works on a laptop with no public URL.
Each unseen message becomes the same `message.received` event the webhook path produces and runs
through the SAME pipeline. Replies (agent auto-sends and Wei's approvals) are delivered from the outbox.

Safety on top of the pipeline's own guardrails:
- Allowlisted senders must pass DKIM or DMARC per Gmail's Authentication-Results header; otherwise
  the pipeline treats them as unknown (held, zero tokens). Anyone can forge a From line.
- Replies go only to the From address the pipeline locked; Reply-To is never used.
- Per-sender and global daily send caps.
- MAILBOX_SEND defaults to "dry-run": replies show in the dashboard outbox but are never transmitted.
- Proper In-Reply-To / References headers so replies stay in the sender's thread.
"""

from __future__ import annotations

import email
import email.policy
import email.utils
import imaplib
import os
import re
import smtplib
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Callable

from .guardrails import domain_of, parse_address, strip_quoted
from .llm import ssl_context

_MSGID_RE = re.compile(r"<[^<>\s]+>")
NET_TIMEOUT = 30  # seconds per IMAP/SMTP network operation
SENT_FOLDER = '"[Gmail]/Sent Mail"'  # Gmail's name in an English-language account


@dataclass
class MailboxConfig:
    address: str
    app_password: str
    display_name: str = "John, Northfield Outdoor Labs"
    send_mode: str = "dry-run"  # dry-run | on
    poll_seconds: int = 60
    imap_host: str = "imap.gmail.com"
    smtp_host: str = "smtp.gmail.com"
    extra_allow: list = field(default_factory=list)
    per_sender_daily_cap: int = 10
    global_daily_cap: int = 50
    grace_hours: float = 2.0  # mail up to this long before the first connection is still handled

    @property
    def sending(self) -> bool:
        return self.send_mode == "on"

    @classmethod
    def from_env(cls, policy: dict) -> "MailboxConfig":
        box = policy.get("mailbox") or {}
        address = os.getenv("GMAIL_ADDRESS", "").strip() or str(box.get("address", ""))
        password = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
        if not address or not password:
            raise SystemExit("--mailbox needs GMAIL_APP_PASSWORD in .env (a Google app password; "
                             "see README, 'Live mailbox').")
        mode = os.getenv("MAILBOX_SEND", "dry-run").strip().lower()
        extra = [str(a).strip().lower() for a in box.get("demo_allow", []) if str(a).strip()]
        personal = os.getenv("MY_PERSONAL_EMAIL", "").strip().lower()
        if personal:
            extra.append(personal)
        return cls(address=address.lower(), app_password=password,
                   display_name=str(box.get("display_name") or cls.display_name),
                   send_mode="on" if mode == "on" else "dry-run",
                   poll_seconds=max(15, int(os.getenv("MAILBOX_POLL_SECONDS", "60"))),
                   extra_allow=extra,
                   per_sender_daily_cap=int(box.get("per_sender_daily_cap", 10)),
                   global_daily_cap=int(box.get("global_daily_cap", 50)))


# ------------------------------------------------------------------ inbound
def _internaldate(parts) -> datetime | None:
    """Arrival time from a FETCH (INTERNALDATE) response, timezone-aware."""
    for p in parts or []:
        line = p[0] if isinstance(p, tuple) else p
        if isinstance(line, bytes):
            hit = imaplib.Internaldate2tuple(line)
            if hit:
                return datetime.fromtimestamp(time.mktime(hit), tz=timezone.utc)
    return None


def authentication(msg: email.message.Message, from_addr: str) -> dict:
    """DKIM/DMARC verdict from the topmost Authentication-Results header written by Gmail (mx.google.com).

    Headers lower down could have been added by the sender, so only Gmail's own stamp counts."""
    for raw in msg.get_all("Authentication-Results") or []:
        value = " ".join(str(raw).split()).lower()
        if not value.startswith("mx.google.com"):
            continue
        dmarc = "dmarc=pass" in value
        from_dom = domain_of(from_addr)
        dkim_domains = re.findall(r"dkim=pass[^;]*?header\.(?:i|d)=@?([a-z0-9.-]+)", value)
        dkim_aligned = any(d == from_dom or from_dom.endswith("." + d) for d in dkim_domains)
        return {"verified": dmarc or dkim_aligned, "dmarc_pass": dmarc, "dkim_aligned": dkim_aligned,
                "header": value[:300]}
    return {"verified": False, "dmarc_pass": False, "dkim_aligned": False, "header": "(no mx.google.com stamp)"}


def _body_parts(msg: email.message.Message) -> tuple[str, str | None, list[dict]]:
    text, html, attachments = "", None, []
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.is_multipart():
            continue
        filename = part.get_filename()
        if filename or part.get_content_disposition() == "attachment":
            attachments.append({"filename": filename or "(unnamed)", "content_type": part.get_content_type()})
            continue
        try:
            content = part.get_content()
        except (LookupError, ValueError):
            content = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
        if part.get_content_type() == "text/plain" and not text:
            text = str(content)
        elif part.get_content_type() == "text/html" and html is None:
            html = str(content)
    return text, html, attachments


def thread_for(msg: email.message.Message, known: Callable[[str], str | None]) -> str:
    """Stable thread id: a known message this one replies to, else the root of its References chain."""
    refs = _MSGID_RE.findall(str(msg.get("References") or ""))
    parent = _MSGID_RE.findall(str(msg.get("In-Reply-To") or ""))
    for mid in parent + list(reversed(refs)):
        thread = known(mid)
        if thread:
            return thread
    root = (refs or parent or _MSGID_RE.findall(str(msg.get("Message-ID") or "")) or [""])[0]
    return "gm_" + re.sub(r"[^A-Za-z0-9]+", "", root)[:40] if root else "gm_" + str(int(time.time()))


def to_event(raw: bytes, inbox: str, known: Callable[[str], str | None]) -> dict:
    """RFC 822 bytes -> the AgentMail-style event the pipeline already understands."""
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    from_header = str(msg.get("From") or "")
    _, from_addr = parse_address(from_header)
    text, html, attachments = _body_parts(msg)
    message_id = (_MSGID_RE.findall(str(msg.get("Message-ID") or "")) or [f"<gm.{int(time.time()*1000)}@local>"])[0]
    try:
        stamp = email.utils.parsedate_to_datetime(str(msg.get("Date"))).isoformat()
    except (TypeError, ValueError):
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    headers = {k: str(msg.get(k)) for k in ("Auto-Submitted", "Precedence", "X-Autoreply", "X-Autorespond",
                                            "List-Id", "References") if msg.get(k) is not None}
    return {
        "type": "event",
        "event_type": "message.received",
        "event_id": "gm_" + re.sub(r"[^A-Za-z0-9]+", "", message_id)[:40],
        "message": {
            "inbox_id": inbox,
            "thread_id": thread_for(msg, known),
            "message_id": message_id,
            "labels": ["received"],
            "timestamp": stamp,
            "from": from_header,
            "to": [str(a) for a in msg.get_all("To") or []],
            "cc": [str(a) for a in msg.get_all("Cc") or []],
            "subject": str(msg.get("Subject") or "(no subject)"),
            "text": text,
            "html": html,
            "attachments": attachments,
            "in_reply_to": (_MSGID_RE.findall(str(msg.get("In-Reply-To") or "")) or [None])[0],
            "headers": headers,
            "source": "gmail",
            "auth": authentication(msg, from_addr),
        },
    }


# ----------------------------------------------------------------- outbound
def build_reply(cfg: MailboxConfig, *, to_addr: str, subject: str, body: str, original: dict) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = email.utils.formataddr((cfg.display_name, cfg.address))
    msg["To"] = to_addr  # the pipeline's locked recipient (authenticated From), never Reply-To
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=cfg.address.split("@")[-1])
    msg["Auto-Submitted"] = "auto-replied"  # tells other robots not to answer us (RFC 3834)
    parent = original.get("message_id")
    if parent:
        refs = _MSGID_RE.findall(str((original.get("headers") or {}).get("References") or ""))
        msg["In-Reply-To"] = parent
        msg["References"] = " ".join(refs + [parent])
    msg.set_content(body)
    return msg


class GmailMailbox:
    def __init__(self, cfg: MailboxConfig, store, *, imap_factory=None, smtp_factory=None, log=print):
        self.cfg, self.store, self.log = cfg, store, log
        # Timeouts matter: without one, a single stalled read froze the poller forever (seen in the first live test).
        self.imap_factory = imap_factory or (lambda host: imaplib.IMAP4_SSL(host, ssl_context=ssl_context(),
                                                                             timeout=NET_TIMEOUT))
        self.smtp_factory = smtp_factory or (lambda host: smtplib.SMTP_SSL(host, 465, context=ssl_context(),
                                                                           timeout=NET_TIMEOUT))

    def cutoff(self) -> datetime:
        """Only mail that arrived after the mailbox was first connected (minus a grace window) is handled.

        A real inbox can hold thousands of old unread emails; answering those would be wrong (and slow), so they
        are left untouched and unread. The first-connect time is saved in the mailbox's own database."""
        saved = self.store.get_settings().get("mailbox_connected_at")
        if not saved:
            saved = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self.store.set_settings({"mailbox_connected_at": saved})
        return datetime.fromisoformat(saved) - timedelta(hours=self.cfg.grace_hours)

    def fetch_new(self) -> list[dict]:
        """Unread inbox mail newer than the cutoff, as events. Each is marked \\Seen only after it is converted."""
        events: list[dict] = []
        cutoff = self.cutoff()
        imap = self.imap_factory(self.cfg.imap_host)
        try:
            imap.login(self.cfg.address, self.cfg.app_password)
            imap.select("INBOX")
            # SINCE is day-granular on the server; the exact cutoff is checked per message below.
            since = (cutoff - timedelta(days=1)).strftime("%d-%b-%Y")
            status, data = imap.uid("SEARCH", None, "UNSEEN", "SINCE", since)
            for uid in (data[0].split() if status == "OK" and data and data[0] else []):
                status, parts = imap.uid("FETCH", uid, "(INTERNALDATE)")
                arrived = _internaldate(parts)
                if status != "OK" or arrived is None or arrived < cutoff:
                    continue  # older than the mailbox connection: leave it alone (stays unread)
                status, parts = imap.uid("FETCH", uid, "(BODY.PEEK[])")
                raw = next((p[1] for p in parts or [] if isinstance(p, tuple)), None)
                if status != "OK" or not raw:
                    continue
                event = to_event(raw, self.cfg.address, self.store.thread_for_message)
                msg = event["message"]
                if parse_address(msg["from"])[1] == self.cfg.address:
                    imap.uid("STORE", uid, "+FLAGS", "\\Seen")  # our own mail (e.g. a copy): never answer ourselves
                    continue
                self.store.remember_message(msg["message_id"], msg["thread_id"])
                events.append(event)
                imap.uid("STORE", uid, "+FLAGS", "\\Seen")
            self._load_sent_history(imap, events)
        finally:
            try:
                imap.logout()
            except Exception:  # noqa: BLE001
                pass
        return events

    def _load_sent_history(self, imap, events: list[dict]) -> None:
        """The usual workflow: Wei emails a supplier first, the agent handles the replies. Gmail keeps Wei's
        email in Sent Mail, not the inbox, so fetch the ones a reply refers to and add them to thread memory."""
        wanted: dict[str, str] = {}
        for event in events:
            msg = event["message"]
            refs = _MSGID_RE.findall(str((msg.get("headers") or {}).get("References") or ""))
            for mid in refs + ([msg["in_reply_to"]] if msg.get("in_reply_to") else []):
                if not self.store.thread_for_message(mid):
                    wanted[mid] = msg["thread_id"]
        if not wanted:
            return
        status, _ = imap.select(SENT_FOLDER, readonly=True)  # read-only: never touches flags
        if status != "OK":
            self.log(f"Gmail: could not open {SENT_FOLDER}; thread memory lacks Wei's own emails")
            return
        for mid, thread in wanted.items():
            status, data = imap.uid("SEARCH", None, "HEADER", "Message-ID", mid)
            uids = data[0].split() if status == "OK" and data and data[0] else []
            if not uids:
                continue
            status, parts = imap.uid("FETCH", uids[0], "(BODY.PEEK[])")
            raw = next((p[1] for p in parts or [] if isinstance(p, tuple)), None)
            if status != "OK" or not raw:
                continue
            sent = email.message_from_bytes(raw, policy=email.policy.default)
            if parse_address(str(sent.get("From") or ""))[1] != self.cfg.address:
                continue
            text, _, _ = _body_parts(sent)
            try:
                when = email.utils.parsedate_to_datetime(str(sent.get("Date"))).astimezone()
                sent_at = when.replace(tzinfo=None).isoformat(timespec="seconds")
            except (TypeError, ValueError):
                sent_at = time.strftime("%Y-%m-%dT%H:%M:%S")
            if self.store.add_history(thread, str(sent.get("To") or ""), str(sent.get("Subject") or ""),
                                      strip_quoted(text) or "(no text)", sent_at, mid):
                self.log(f"Gmail: added Wei's sent email '{sent.get('Subject')}' to thread memory")

    def deliver_pending(self) -> list[dict]:
        """Send outbox replies for Gmail threads (agent auto-sends and Wei's approvals), within the caps."""
        results = []
        pending = self.store.pending_deliveries(source="gmail")
        if not pending:
            return results
        smtp = None
        try:
            for item in pending:
                to_addr = item["to_addr"]
                if not self.cfg.sending:
                    self.store.mark_delivery(item["id"], "dry_run")
                    self.log(f"[dry-run] reply to {to_addr} NOT sent: {item['subject']}")
                    results.append({"id": item["id"], "status": "dry_run"})
                    continue
                if self.store.deliveries_today(to_addr) >= self.cfg.per_sender_daily_cap:
                    self.store.mark_delivery(item["id"], "capped_sender")
                    self.log(f"daily cap reached for {to_addr}: reply NOT sent")
                    results.append({"id": item["id"], "status": "capped_sender"})
                    continue
                if self.store.deliveries_today() >= self.cfg.global_daily_cap:
                    self.store.mark_delivery(item["id"], "capped_global")
                    self.log("global daily send cap reached: reply NOT sent")
                    results.append({"id": item["id"], "status": "capped_global"})
                    continue
                reply = build_reply(self.cfg, to_addr=to_addr, subject=item["subject"], body=item["body"],
                                    original=item["email"])
                if smtp is None:
                    smtp = self.smtp_factory(self.cfg.smtp_host)
                    smtp.login(self.cfg.address, self.cfg.app_password)
                smtp.send_message(reply, from_addr=self.cfg.address, to_addrs=[to_addr])
                self.store.mark_delivery(item["id"], "sent", reply["Message-ID"])
                self.store.remember_message(reply["Message-ID"], item["thread_id"])
                self.log(f"reply sent to {to_addr}: {item['subject']}")
                results.append({"id": item["id"], "status": "sent"})
        finally:
            if smtp is not None:
                try:
                    smtp.quit()
                except Exception:  # noqa: BLE001
                    pass
        return results


def check_login(cfg: MailboxConfig) -> None:
    """Fail fast with a readable message if the app password is wrong."""
    imap = imaplib.IMAP4_SSL(cfg.imap_host, ssl_context=ssl_context(), timeout=NET_TIMEOUT)
    try:
        imap.login(cfg.address, cfg.app_password)
    except imaplib.IMAP4.error as exc:
        raise SystemExit(f"Gmail login failed for {cfg.address}: {exc}. Check GMAIL_APP_PASSWORD "
                         "(a 16-character app password, not your normal password).") from None
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass
