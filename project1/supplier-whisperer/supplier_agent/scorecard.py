"""Supplier scorecard: is this supplier responsive, knowledgeable and reliable?

Calibrated on two real sourcing threads for the same part (kept private). One supplier replied within minutes
but was a trader relaying to a factory: it kept answering "I'll ask the factory", contradicted its own spec
sheet and stalled. The other replied more slowly but answered with numbers, drafted documents, sent photos
unprompted and delivered. Speed alone picks the wrong one, so the score weighs substance and follow-through
as much as reply time. Everything here is deterministic code: no model call, no tokens.

Input: one supplier's conversation as messages {"role": "buyer"|"supplier", "at": ISO time, "text": str,
"attachment": optional kind}. "buyer" is Wei (or the agent writing for him).
"""

from __future__ import annotations

import re
from datetime import datetime
from statistics import median

# Wei had to chase: "hello?", "any update?", "?" on its own.
_NUDGE_RE = re.compile(r"^\s*(?:hello\??|hi\??|\?+|any update\??|hi,? do you have any update\??|keep me posted\.?|"
                       r"following up\.?|just checking in\.?)\s*$", re.I)
# The supplier doesn't know, or passes the question on.
_GAP_RE = re.compile(r"\b(?:i don'?t know|not sure|difficult (?:for me )?to communicate|ask (?:the )?factory|"
                     r"check with (?:the )?factory|factory hasn'?t|couldn'?t find|cannot be done|no idea)\b", re.I)
# The supplier promises to come back.
_PROMISE_RE = re.compile(r"\b(?:i'?ll|i will|let me|we will)\s+(?:ask|check|confirm|share|send|update|try|get back)\b",
                         re.I)
# Technical substance: a number with a unit, or a standard / material name.
_TECH_RE = re.compile(r"\d+(?:\.\d+)?\s?(?:mm|cm|m\b|awg|v\b|kv|a\b|w\b|°|℃|%|mpa|hz|khz|mhz|g\b|kg|pcs|days|"
                      r"cps)|\b(?:abs|ul94|ip6\d|copper|stainless|epoxy|m8|enig|ipc)\b", re.I)
_QUESTION_RE = re.compile(r"\?|^\s*\d+[.)]\s", re.M)


def _ts(value) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text[:25] if "%z" in fmt else text[:19], fmt).replace(tzinfo=None)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return None


def _turns(messages: list[dict]) -> list[dict]:
    """Merge consecutive messages from the same side into one turn (chat apps split one answer into lines)."""
    turns: list[dict] = []
    for m in sorted(messages, key=lambda m: _ts(m.get("at")) or datetime.min):
        at = _ts(m.get("at"))
        text = (m.get("text") or "").strip()
        if turns and turns[-1]["role"] == m["role"]:
            turns[-1]["texts"].append(text)
            turns[-1]["attachments"] += 1 if m.get("attachment") else 0
            turns[-1]["end"] = at or turns[-1]["end"]
        else:
            turns.append({"role": m["role"], "start": at, "end": at, "texts": [text],
                          "attachments": 1 if m.get("attachment") else 0})
    return turns


def _substantive(turn: dict) -> bool:
    text = " ".join(turn["texts"])
    return bool(_TECH_RE.search(text)) or turn["attachments"] > 0 or len(text.split()) >= 25


def score(messages: list[dict], ghost_hours: float = 72.0, now: datetime | None = None) -> dict:
    now = (now or datetime.now()).replace(tzinfo=None)
    turns = _turns(messages)
    buyer_msgs = [m for m in messages if m["role"] == "buyer"]
    supplier_msgs = [m for m in messages if m["role"] == "supplier"]
    reply_hours, ghosted, asked, answered = [], 0, 0, 0
    for i, t in enumerate(turns):
        if t["role"] != "buyer":
            continue
        nxt = turns[i + 1] if i + 1 < len(turns) else None
        has_question = bool(_QUESTION_RE.search(" ".join(t["texts"])))
        if nxt is None or nxt["role"] != "supplier" or not (t["end"] and nxt["start"]):
            # No reply yet: only counts against the supplier once it is overdue, not minutes after we wrote.
            overdue = t["end"] is not None and (now - t["end"]).total_seconds() / 3600 > ghost_hours
            if has_question and overdue:
                ghosted += 1
                asked += 1
            continue
        hours = (nxt["start"] - t["end"]).total_seconds() / 3600
        reply_hours.append(hours)
        if hours > ghost_hours:
            ghosted += 1
        if has_question:
            asked += 1
            # Answered = the supplier's next turn (or the one after a quick "ok") carries substance.
            later = [x for x in turns[i + 1:i + 4] if x["role"] == "supplier"]
            answered += 1 if any(_substantive(x) for x in later) else 0
    supplier_text = [m.get("text") or "" for m in supplier_msgs]
    gaps = sum(1 for s in supplier_text if _GAP_RE.search(s))
    promises = sum(1 for s in supplier_text if _PROMISE_RE.search(s))
    technical = sum(1 for s in supplier_text if _TECH_RE.search(s))
    documents = sum(1 for m in supplier_msgs if m.get("attachment") in ("file", "image", "video"))
    nudges = sum(1 for m in buyer_msgs if _NUDGE_RE.match(m.get("text") or ""))

    med = median(reply_hours) if reply_hours else None
    answer_rate = answered / asked if asked else None
    # 0-100 sub-scores. Speed matters, but less than substance: a fast "I'll ask the factory" is not an answer.
    speed = (100 if med is not None and med <= 4 else 80 if med is not None and med <= 24 else
             50 if med is not None and med <= 72 else 20)
    knowledge = round(100 * technical / max(1, technical + gaps)) if (technical or gaps) else 50
    reliability = max(0, 100 - 15 * ghosted - 10 * nudges - 10 * max(0, gaps - documents))
    answers = round(100 * answer_rate) if answer_rate is not None else 50
    overall = round(0.2 * speed + 0.3 * answers + 0.3 * knowledge + 0.2 * reliability)

    notes = []
    if med is not None:
        notes.append(f"Median reply {med:.1f} h" + (" (fast)" if med <= 4 else " (slow)" if med > 24 else ""))
    if asked:
        notes.append(f"Answered {answered}/{asked} of your questions with substance")
    if gaps:
        notes.append(f"{gaps} 'don't know / ask the factory' replies")
    if ghosted:
        notes.append(f"{ghosted} time(s) no reply within {ghost_hours:.0f} h")
    if nudges:
        notes.append(f"You had to chase {nudges} time(s)")
    if documents:
        notes.append(f"Shared {documents} photos/files")
    return {
        "overall": overall,
        "subscores": {"speed": speed, "answers": answers, "knowledge": knowledge, "reliability": reliability},
        "median_reply_hours": round(med, 2) if med is not None else None,
        "questions_asked": asked, "questions_answered": answered,
        "knowledge_gaps": gaps, "promises": promises, "technical_messages": technical,
        "documents_shared": documents, "nudges_needed": nudges, "ghosted": ghosted,
        "messages": {"buyer": len(buyer_msgs), "supplier": len(supplier_msgs)},
        "notes": notes,
    }
