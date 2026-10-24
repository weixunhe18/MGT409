"""Anonymize an Alibaba chat export (HTML) into a private evaluation thread.

    python scripts/anonymize_chat.py data/raw_private/supplier_01/chat_export.html \
        --map data/raw_private/supplier_01/replacements.json --out data/raw_private/supplier_01/anonymized

The replacement map is a JSON object {"real text": "[PLACEHOLDER]", ...}. It holds the real names and
numbers, so it lives next to the raw export in the git-ignored data/raw_private/ folder, never in this script.
On top of the map, generic patterns catch emails, phone-like numbers, long IDs and URL query strings.

Writes thread.json (every message), thread.md (for human review) and events.json (each run of consecutive
supplier messages as one AgentMail-style inbound email, ready to replay through the pipeline). Then it scans
the output for anything from the map or the generic patterns and exits non-zero if something leaked.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
LONG_NUMBER_RE = re.compile(r"(?<![\w.])(?:\+?\d[\d -]{6,}\d)(?![\w.])")  # phones, order ids, tracking numbers
TRACKING_RE = re.compile(r"\b1Z[0-9A-Z]{16}\b")  # UPS
QUERY_RE = re.compile(r"(https?://[^\s?#\"<>]+)[?#][^\s\"<>)]*")
SUPPLIER_GAP = timedelta(hours=3)  # supplier messages closer than this form one "email"


class _ExportParser(HTMLParser):
    """Collects <article class="message buyer|supplier"> blocks: time, body text, quoted text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.messages: list[dict] = []
        self._cur: dict | None = None
        self._field: str | None = None
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if tag == "article" and "message" in classes:
            self._cur = {"role": "buyer" if "buyer" in classes else "supplier", "at": "", "body": "", "quoted": ""}
        elif self._cur is not None:
            if tag == "time":
                self._field = "at"
            elif tag == "div" and "body" in classes:
                self._field, self._depth = "body", 1
            elif tag == "blockquote":
                self._field = "quoted"
            elif tag == "div" and self._field == "body":
                self._depth += 1
            elif tag == "br" and self._field in ("body", "quoted"):
                self._cur[self._field] += "\n"
            elif tag == "a" and self._field in ("body", "quoted") and a.get("href"):
                self._cur[self._field] += " "

    def handle_endtag(self, tag):
        if self._cur is None:
            return
        if tag == "article":
            self.messages.append(self._cur)
            self._cur, self._field = None, None
        elif tag == "time" and self._field == "at":
            self._field = None
        elif tag == "div" and self._field == "body":
            self._depth -= 1
            if self._depth == 0:
                self._field = None
        elif tag == "blockquote" and self._field == "quoted":
            self._field = None

    def handle_data(self, data):
        if self._cur is not None and self._field:
            self._cur[self._field] += data


def parse_export(path: Path) -> list[dict]:
    parser = _ExportParser()
    parser.feed(path.read_text(encoding="utf-8"))
    out = []
    for i, m in enumerate(parser.messages, 1):
        body = html.unescape(m["body"]).replace("&lt;", "<").replace("&gt;", ">")
        quoted = html.unescape(m["quoted"]).replace("<br/>", "\n").strip()
        quoted = re.sub(r"^Quoted message\s*", "", quoted)
        attachment = None
        hit = re.search(r"\[(image|file|video)[^\]]*\]", body, re.I)
        if hit and len(body.strip()) < 60:
            attachment, body = hit.group(1).lower(), ""
        out.append({"i": i, "at": m["at"].strip(), "role": m["role"], "text": _tidy(body),
                    "quoted": _tidy(quoted), "attachment": attachment})
    return out


def _tidy(text: str) -> str:
    lines = [ln.rstrip() for ln in text.replace("\r", "").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def anonymize(text: str, mapping: dict[str, str]) -> str:
    # Whole email addresses first: mapping only the domain would leave "sales2@[DOMAIN]".
    text = EMAIL_RE.sub("[EMAIL]", text)
    # Longest keys first, so a full name wins over the first name alone.
    for real in sorted(mapping, key=len, reverse=True):
        text = re.sub(re.escape(real), mapping[real], text, flags=re.I)
    text = QUERY_RE.sub(r"\1", text)
    text = TRACKING_RE.sub("[TRACKING_NO]", text)
    return LONG_NUMBER_RE.sub("[NUMBER]", text)


def to_events(messages: list[dict], subject: str, sender: str) -> list[dict]:
    """Each run of supplier messages (no buyer message in between, gaps < 3 h) becomes one inbound email."""
    events, run, thread = [], [], "thr_private_supplier"

    def flush():
        if not run:
            return
        n = len(events) + 1
        body = "\n\n".join(m["text"] or f"[{m['attachment']} attachment]" for m in run)
        events.append({
            "type": "event", "event_type": "message.received", "event_id": f"evt_private_{n:03d}",
            "_source_messages": [m["i"] for m in run],
            "message": {"inbox_id": "wei@northfield-labs.example", "thread_id": thread,
                        "message_id": f"<private.{n:03d}@supplier.example>", "labels": ["received"],
                        "timestamp": run[0]["at"], "from": sender, "to": ["Wei He <wei@northfield-labs.example>"],
                        "cc": [], "subject": subject if n == 1 else f"RE: {subject}", "text": body, "html": None,
                        "attachments": [{"filename": f"{m['attachment']}_{m['i']}"} for m in run if m["attachment"]],
                        "in_reply_to": None, "headers": {}},
        })
        run.clear()

    last = None
    for m in messages:
        if m["role"] != "supplier":
            flush()
            last = None
            continue
        at = _when(m["at"])
        if run and last and at and at - last > SUPPLIER_GAP:
            flush()
        run.append(m)
        last = at
    flush()
    return events


def _when(stamp: str) -> datetime | None:
    try:
        return datetime.strptime(stamp, "%Y-%m-%d %H:%M %z")
    except ValueError:
        return None


STAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?(?: ?[+-]\d{2}:\d{2})?")  # our own timestamps


def leaks(text: str, mapping: dict[str, str]) -> list[str]:
    text = STAMP_RE.sub("", text)
    found = [real for real in mapping if real.lower() in text.lower()]
    found += EMAIL_RE.findall(text.replace("@northfield-labs.example", "").replace("@supplier.example", ""))
    found += [n for n in LONG_NUMBER_RE.findall(text)]
    found += TRACKING_RE.findall(text)
    return found


def to_markdown(messages: list[dict], title: str) -> str:
    out = [f"# {title}", "", f"{len(messages)} messages. PRIVATE: local evaluation only, never commit.", ""]
    for m in messages:
        who = "**Buyer (Wei)**" if m["role"] == "buyer" else "**Supplier**"
        out.append(f"### {m['i']}. {who} · {m['at']}")
        if m["attachment"]:
            out.append(f"*[{m['attachment']} attachment]*")
        if m["text"]:
            out.append(m["text"])
        if m["quoted"]:
            out.append("> " + m["quoted"].replace("\n", "\n> "))
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("export", type=Path)
    ap.add_argument("--map", type=Path, required=True, help="private JSON {real text: placeholder}")
    ap.add_argument("--out", type=Path, required=True)
    # Keep it neutral: the topic detector reads subjects too, so "pricing" here would tag every email as price.
    ap.add_argument("--subject", default="Water leak sensor samples")
    ap.add_argument("--sender", default="Supplier Rep <rep@supplier.example>")
    args = ap.parse_args(argv)

    mapping = json.loads(args.map.read_text(encoding="utf-8"))
    messages = parse_export(args.export)
    for m in messages:
        m["text"], m["quoted"] = anonymize(m["text"], mapping), anonymize(m["quoted"], mapping)
    events = to_events(messages, args.subject, args.sender)

    args.out.mkdir(parents=True, exist_ok=True)
    files = {
        "thread.json": json.dumps(messages, ensure_ascii=False, indent=1),
        "thread.md": to_markdown(messages, "Supplier thread (anonymized)"),
        "events.json": json.dumps(events, ensure_ascii=False, indent=1),
    }
    problems = []
    for name, content in files.items():
        (args.out / name).write_text(content, encoding="utf-8")
        problems += [f"{name}: {hit}" for hit in leaks(content, mapping)]
    print(f"{len(messages)} messages · {sum(m['role'] == 'supplier' for m in messages)} from the supplier · "
          f"{len(events)} supplier 'emails' · written to {args.out}")
    if problems:
        print("POSSIBLE LEAKS (fix the map and re-run):\n  " + "\n  ".join(problems))
        return 1
    print("Leak scan: clean (no mapped names, emails, phone-like numbers or tracking numbers).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
