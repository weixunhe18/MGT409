"""The four agents: manager (triage), internal context (spec Q&A), email drafter, compliance reviewer.

Each agent has a live path (gpt-6-luna via Portkey) and a deterministic offline path (mock mode).
Whatever the model says, deterministic code merges in its own topic detection afterwards, so the
model can add escalation topics but never remove them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .config import PROMPTS_DIR
from .guardrails import HARD_TOPICS, TOPIC_LABELS, detect_topics, extract_questions
from .knowledge import KnowledgeBase
from .llm import LLMError, Meter

_DELIMS_RE = re.compile(r"</?\s*(supplier_email|draft)\b[^>]*>", re.I)
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
# Whole tokens containing a digit: "0.1", "25%", "SPI-C1", "MT-11010" (not the bare "1" inside "SPI-C1").
_CODE_TOKEN_RE = re.compile(r"[A-Za-z0-9%]*\d[A-Za-z0-9%]*(?:[.\-][A-Za-z0-9%]*\d?[A-Za-z0-9%]*)*")


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def render(template: str, **values) -> str:
    # str.replace, not str.format: the prompts contain literal JSON braces.
    for key, value in values.items():
        template = template.replace("{" + key + "}", str(value))
    return template


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "yes", "1")


def _as_float(value, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def human_join(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


@dataclass
class AgentContext:
    email: dict
    kb: KnowledgeBase
    policy: dict
    llm: object  # MockLLM | PortkeyLLM
    meter: Meter
    thread: list = field(default_factory=list)

    @property
    def owner(self) -> dict:
        return self.policy.get("owner", {})

    @property
    def owner_first(self) -> str:
        return self.owner.get("first_name") or self.owner.get("name", "the engineer").split()[0]

    @property
    def signature(self) -> str:
        return str(self.policy.get("assistant_signature", "")).strip()


def spotlight(email: dict) -> str:
    """Wrap untrusted supplier text in delimiters the model is told never to obey."""
    body = _DELIMS_RE.sub("[removed tag]", email.get("visible_text") or "")
    subject = _DELIMS_RE.sub("[removed tag]", email.get("subject") or "")
    sender = f"{email.get('from_name') or ''} <{email.get('from_addr') or ''}>".strip()
    return (f"<supplier_email>\nFrom: {sender}\nSubject: {subject}\n\n{body.strip()}\n</supplier_email>")


# ------------------------------------------------------------------ manager
def _clean_triage(raw: dict) -> dict:
    questions = []
    for q in raw.get("questions") or []:
        if isinstance(q, str):
            q = {"text": q}
        if not isinstance(q, dict):
            continue
        text = str(q.get("text") or "").strip()
        if not text:
            continue
        topics = [t for t in (q.get("topics") or []) if t in HARD_TOPICS]
        questions.append({"id": len(questions) + 1, "text": text[:500], "topics": topics,
                          "engineering_change": _as_bool(q.get("engineering_change"))})
        if len(questions) >= 10:
            break
    return {
        "summary": str(raw.get("summary") or "")[:400],
        "intent": str(raw.get("intent") or "other")[:40],
        "questions": questions,
        "suspicious_instructions": _as_bool(raw.get("suspicious_instructions")),
        "reply_needed": raw.get("reply_needed") is None or _as_bool(raw.get("reply_needed")),
        "urgency": str(raw.get("urgency") or "normal")[:10],
    }


def heuristic_triage(email: dict) -> dict:
    body = email.get("visible_text") or ""
    questions = []
    for text in extract_questions(body):
        topics = detect_topics(text)
        questions.append({"id": len(questions) + 1, "text": text,
                          "topics": [t for t in HARD_TOPICS if t in topics],
                          "engineering_change": "engineering_change" in topics})
    email_topics = detect_topics(body)
    hard = [t for t in HARD_TOPICS if t in email_topics]
    if any(t in hard for t in ("price", "quantity", "po")):
        intent = "commercial"
    elif "payment" in hard:
        intent = "payment"
    elif "date" in hard:
        intent = "schedule"
    elif "drawing" in hard:
        intent = "document_request"
    elif questions:
        intent = "technical_question"
    else:
        intent = "other"
    first_line = next((ln.strip() for ln in body.splitlines()
                       if ln.strip() and not re.match(r"^(hi|hello|dear)\b", ln.strip(), re.I)), "")
    summary = (first_line[:180] + "…") if len(first_line) > 180 else first_line
    return {
        "summary": summary,
        "intent": intent,
        "questions": questions,
        "suspicious_instructions": False,
        "reply_needed": bool(questions or hard),
        "urgency": "high" if re.search(r"\b(urgent|asap|today|tomorrow)\b", body, re.I) else "normal",
    }


def merge_deterministic(triage: dict, email: dict) -> dict:
    """Union the model's topics with regex topics. Code can add escalations, never remove them."""
    email_topics = detect_topics((email.get("subject") or "") + "\n" + (email.get("visible_text") or ""))
    for q in triage["questions"]:
        qt = detect_topics(q["text"])
        q["topics"] = [t for t in HARD_TOPICS if t in qt or t in q["topics"]]
        q["engineering_change"] = bool(q["engineering_change"] or "engineering_change" in qt)
    hard = {t for q in triage["questions"] for t in q["topics"]} | {t for t in HARD_TOPICS if t in email_topics}
    triage["hard_topics"] = [t for t in HARD_TOPICS if t in hard]
    triage["topic_evidence"] = {t: email_topics.get(t, []) for t in triage["hard_topics"]}
    triage["engineering_change"] = bool(any(q["engineering_change"] for q in triage["questions"])
                                        or "engineering_change" in email_topics)
    # Did the supplier actually ask or request something? Kept separately because a hard topic forces
    # reply_needed below, and a holding reply to a pure status update is just noise (real-thread replay).
    triage["supplier_asked"] = bool(triage["questions"]) and bool(triage.get("reply_needed", True))
    if triage["hard_topics"]:
        triage["reply_needed"] = True
    return triage


def run_manager(ctx: AgentContext) -> tuple[dict, dict]:
    instructions = render(load_prompt("manager"), owner_name=ctx.owner.get("name", ""),
                          owner_first=ctx.owner_first, company=ctx.owner.get("company", ""))
    input_text = spotlight(ctx.email)
    if ctx.llm.live:
        raw, call = ctx.llm.complete_json(agent="manager", instructions=instructions, input_text=input_text,
                                          meter=ctx.meter, max_output_tokens=6000)
        triage = _clean_triage(raw)
        if not triage["questions"]:
            # Fall back to deterministic extraction rather than silently dropping questions.
            triage["questions"] = heuristic_triage(ctx.email)["questions"]
    else:
        triage = heuristic_triage(ctx.email)
        call = ctx.llm.record_estimate(ctx.meter, "manager", instructions, input_text, triage)
    return merge_deterministic(triage, ctx.email), call


# ------------------------------------------------------------------ context
def _empty_answer() -> dict:
    return {"answerable": False, "answer": "", "source": "", "confidence": 0.0, "label": ""}


def run_context(ctx: AgentContext, questions: list[dict]) -> tuple[dict, dict | None]:
    askable = [q for q in questions if not q["topics"]]
    if not askable:
        return {}, None
    answers: dict[int, dict] = {}
    if ctx.llm.live:
        instructions = render(load_prompt("context"), product_name=ctx.policy.get("product_name", ""),
                              shareable_spec=ctx.kb.shareable_text())
        input_text = json.dumps({"questions": [{"id": q["id"], "text": q["text"]} for q in askable]},
                                ensure_ascii=False)
        raw, call = ctx.llm.complete_json(agent="context", instructions=instructions, input_text=input_text,
                                          meter=ctx.meter, max_output_tokens=6000)
        for a in raw.get("answers") or []:
            if not isinstance(a, dict):
                continue
            try:
                qid = int(a.get("id"))
            except (TypeError, ValueError):
                continue
            text = str(a.get("answer") or "").strip()
            answers[qid] = {"answerable": _as_bool(a.get("answerable")) and bool(text), "answer": text[:600],
                            "source": str(a.get("source") or "")[:120],
                            "confidence": _as_float(a.get("confidence")), "label": ""}
    else:
        for q in askable:
            match = ctx.kb.search(q["text"])
            if match is None:
                answers[q["id"]] = {**_empty_answer(), "note": "not covered by the spec"}
            elif match.fact.tbd:
                answers[q["id"]] = {**_empty_answer(), "source": match.fact.section, "label": match.fact.label,
                                    "confidence": match.confidence, "note": "spec says TBD"}
            else:
                answers[q["id"]] = {"answerable": True, "answer": match.fact.text, "label": match.fact.label,
                                    "source": match.fact.section, "confidence": match.confidence}
        instructions = render(load_prompt("context"), product_name=ctx.policy.get("product_name", ""),
                              shareable_spec=ctx.kb.shareable_text())
        call = ctx.llm.record_estimate(ctx.meter, "context", instructions,
                                       json.dumps([q["text"] for q in askable]), answers)
    for q in askable:
        answers.setdefault(q["id"], {**_empty_answer(), "note": "model gave no answer"})
    # Anti-hallucination: every number in an answer must exist in the shareable spec.
    spec_numbers = set(_NUMBER_RE.findall(ctx.kb.shareable_text()))
    for a in answers.values():
        if a["answerable"]:
            missing = [n for n in _NUMBER_RE.findall(a["answer"]) if n not in spec_numbers]
            a["grounded"] = not missing
            a["ungrounded_numbers"] = missing
            if missing:
                a["confidence"] = min(a["confidence"], 0.4)
    return answers, call


# ------------------------------------------------------------------ drafter
# What Wei usually needs to know before he decides. The agent asks the supplier for it instead of only
# saying "Wei will reply", so Wei's decision is better informed and nobody waits a round trip (D8).
# Payment and identity get no questions: asking a supplier about bank details invites fraud.
SUPPLIER_QUESTIONS = {
    "engineering_change": "What is the reason for this proposal, and how would it affect cost, lead time, quality "
                          "and reliability? Do you have test data or samples that show the result?",
    "price": "Could you share a cost breakdown (part, tooling, packaging and freight), price breaks by quantity, "
             "the Incoterm, and how long this price is valid?",
    "quantity": "What minimum quantity applies, and what drives it (material lots, line setup or tooling)?",
    "date": "What is the earliest date you can support, and what are the main drivers of the lead time?",
    "po": "What information do you need from us for an order, and what are the next steps on your side?",
    "drawing": "Which features or dimensions are unclear, and which process step do they affect?",
}


def supplier_questions(triage: dict, limit: int = 3) -> list[str]:
    keys = (["engineering_change"] if triage.get("engineering_change") else []) + list(triage.get("hard_topics", []))
    return [SUPPLIER_QUESTIONS[k] for k in keys if k in SUPPLIER_QUESTIONS][:limit]


_REQUEST_LINE_RE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+(.+)$|^(.*\?)\s*$|^\s*(please (?:send|share|provide) .+)$",
                              re.I | re.M)
_SUBSTANCE_RE = re.compile(r"\d+(?:\.\d+)?\s?(?:mm|µm|um|gsm|awg|v\b|mah|%|°|days|pcs)|\b(?:datasheet|report|"
                           r"certificate|summary|test data|attached|see below)\b", re.I)


def still_waiting_for(thread: list[dict], email: dict) -> list[str]:
    """Wei's requests from his last email in this thread, if the supplier's reply delivers none of it.

    Real pattern: a supplier goes quiet for weeks, then writes "any update?" without answering anything.
    The useful reply re-asks for what Wei is still waiting for instead of saying "still open"."""
    if email.get("attachments") or _SUBSTANCE_RE.search(email.get("visible_text") or email.get("text") or ""):
        return []
    wei = [h for h in thread if h.get("direction") == "outbound" and str(h.get("from", "")).startswith("Wei")]
    if not wei:
        return []
    asks = []
    for m in _REQUEST_LINE_RE.finditer(wei[-1].get("body") or ""):
        text = next(g for g in m.groups() if g).strip().rstrip(".")
        if len(text) > 8 and not text.lower().startswith(("hi ", "thanks", "thank you")):
            asks.append(text)
    return asks[:5]


def build_plan(triage: dict, answers: dict) -> dict:
    answered, open_items, decisions = [], [], []
    for q in triage["questions"]:
        if q["topics"]:
            decisions.append(q)
        elif answers.get(q["id"], {}).get("answerable"):
            answered.append(q)
        else:
            open_items.append(q)
    return {"answered": answered, "open": open_items, "decisions": decisions,
            "decision_topics": triage.get("hard_topics", []), "ask": supplier_questions(triage)}


def heuristic_draft(ctx: AgentContext, triage: dict, answers: dict) -> str:
    email, first = ctx.email, ctx.owner_first
    supplier_first = (email.get("from_name") or "").split()[0] if email.get("from_name") else ""
    plan = build_plan(triage, answers)
    waiting = still_waiting_for(ctx.thread, email)
    lines = [f"Hi {supplier_first}," if supplier_first else "Hello,", "", "Thank you for your email."]
    if waiting and not plan["answered"]:
        lines += ["", f"We are still waiting for these items from {first}'s earlier email:", ""]
        lines += [f"{i}. {w}" for i, w in enumerate(waiting, 1)]
        lines += ["", "Could you please send them, or tell us when you expect to have them?"]
    elif plan["answered"] or plan["open"]:
        product = ctx.policy.get("product_name") or "product"
        lines += ["", f"Please see our answers below, based on the current {product} requirements:", ""]
        for q in triage["questions"]:
            if q["topics"]:
                continue
            a = answers.get(q["id"]) or {}
            if a.get("answerable"):
                text = f"{a['label']}: {a['answer']}" if a.get("label") else a["answer"]
                if q.get("engineering_change"):
                    text += f" I have passed your proposal to {first} for review."
                lines.append(f"{q['id']}. {text}")
            else:
                lines.append(f"{q['id']}. This point is still open on our side. I have flagged it for {first}, "
                             "who will follow up with you.")
    if plan["decision_topics"]:
        # Identity questions are never named in the reply; Wei answers those personally.
        labels = human_join([TOPIC_LABELS[t] for t in plan["decision_topics"] if t != "identity"])
        ids = [q["id"] for q in plan["decisions"]]
        if not labels:
            lines += ["", f"{first} will reply to you directly."]
            lines += ["", "Best regards,", ctx.signature]
            return "\n".join(lines).strip()
        if ids and len(ids) < len(triage["questions"]):
            word = "Points" if len(ids) > 1 else "Point"
            verb = "need" if len(ids) > 1 else "needs"
            sentence = f"{word} {human_join([str(i) for i in ids])} ({labels}) {verb} {first}'s decision"
        else:
            sentence = f"Your questions on {labels} need {first}'s decision"
        lines += ["", f"{sentence}, so I have flagged them and {first} will reply to you directly."]
    if plan["ask"]:
        lines += ["", f"To help {first} review this, could you please share:"]
        lines += [f"- {q}" for q in plan["ask"]]
    lines += ["", "Best regards,", ctx.signature]
    return "\n".join(lines).strip()


def _squash(text: str) -> str:
    return " ".join(text.lower().split())


def ensure_signature(body: str, signature: str) -> str:
    # Full-signature match: a bare first line ("John") would also match a supplier called "Johnny".
    if signature.strip() and _squash(signature) not in _squash(body):
        body = body.rstrip() + "\n\nBest regards,\n" + signature.strip()
    return body


def run_drafter(ctx: AgentContext, triage: dict, answers: dict) -> tuple[str, dict]:
    persona = ctx.policy.get("persona") or {}
    instructions = render(load_prompt("drafter"), owner_name=ctx.owner.get("name", ""),
                          owner_title=ctx.owner.get("title", ""), company=ctx.owner.get("company", ""),
                          owner_first=ctx.owner_first, signature=ctx.signature,
                          persona_name=persona.get("name", "the supply chain team"),
                          persona_title=persona.get("title", "Supply Chain"))
    plan = build_plan(triage, answers)
    approved = [{"id": q["id"], "question": q["text"], "answer": answers[q["id"]]["answer"],
                 "note": "supplier proposed a change: say it was passed to the engineer for review"
                 if q.get("engineering_change") else ""} for q in plan["answered"]]
    history = "\n".join(f"- {h['direction']} from {h['from']}: {h['body'][:300]}" for h in ctx.thread[-4:]) or "(none)"
    input_text = (
        spotlight(ctx.email)
        + "\n\nEARLIER MESSAGES IN THIS THREAD:\n" + history
        + "\n\nAPPROVED ANSWERS (only facts you may use):\n" + json.dumps(approved, ensure_ascii=False, indent=1)
        + "\n\nOPEN ITEMS (say still open, engineer will follow up):\n"
        + json.dumps([{"id": q["id"], "question": q["text"]} for q in plan["open"]], ensure_ascii=False)
        + "\n\nNEEDS DECISION (engineer will reply directly; do not answer):\n"
        + json.dumps({"question_ids": [q["id"] for q in plan["decisions"]],
                      "topics": [TOPIC_LABELS[t] for t in plan["decision_topics"]]}, ensure_ascii=False)
        + "\n\nQUESTIONS TO ASK THE SUPPLIER (so the engineer can decide; ask them, adapted to this email):\n"
        + json.dumps(plan["ask"], ensure_ascii=False)
        + "\n\nSTILL WAITING FOR (the engineer asked for these in his last email; the supplier has not delivered them; "
          "list them and ask again politely, with a request for a date):\n"
        + json.dumps(still_waiting_for(ctx.thread, ctx.email), ensure_ascii=False)
    )
    if ctx.llm.live:
        raw, call = ctx.llm.complete_json(agent="drafter", instructions=instructions, input_text=input_text,
                                          meter=ctx.meter, max_output_tokens=6000)
        body = str(raw.get("body") or "").strip()
        if not body:
            raise LLMError("drafter returned an empty body")
    else:
        body = heuristic_draft(ctx, triage, answers)
        call = ctx.llm.record_estimate(ctx.meter, "drafter", instructions, input_text, {"body": body})
    return ensure_signature(body, ctx.signature), call


# --------------------------------------------------------------- compliance
def _spec_lines_for(kb, answer: str) -> list[str]:
    """Labelled shareable spec lines behind an answer, so the reviewer sees what each number applies to.

    Short answers ("0.1 mm maximum", "SPI-C1") often lack label words, so match on whole number/code tokens first."""
    def code_tokens(text: str) -> set[str]:
        return {t.rstrip(".-") for t in _CODE_TOKEN_RE.findall(text)}

    tokens = code_tokens(answer)
    if tokens:
        lines = [f.display for f in kb.facts if tokens <= code_tokens(f.display)]
        if lines:
            return lines[:2]
    match = kb.search(answer)
    return [match.fact.display] if match else []


def run_compliance_review(ctx: AgentContext, body: str, hard_topics: list[str],
                          answers: dict | None = None) -> tuple[dict, dict]:
    """Second-opinion LLM review. It sees the draft and the approved spec facts, never the supplier email."""
    instructions = render(load_prompt("compliance"), owner_name=ctx.owner.get("name", ""), owner_first=ctx.owner_first,
                          signature=ctx.signature)
    safe_body = _DELIMS_RE.sub("[removed tag]", body)
    # Only spec-derived text (answer, section, and the spec line it came from) goes in, never the supplier's wording.
    facts = []
    for a in (answers or {}).values():
        if a.get("answerable"):
            facts.append({"fact": a["answer"], "source": a.get("source", ""),
                          "spec_lines": _spec_lines_for(ctx.kb, a["answer"])})
    input_text = (f"<draft>\n{safe_body}\n</draft>\n\nAPPROVED SPEC FACTS:\n"
                  f"{json.dumps(facts, ensure_ascii=False, indent=1) if facts else '(none)'}\n\n"
                  f"Topics the supplier raised that must NOT be committed to: "
                  f"{', '.join(TOPIC_LABELS[t] for t in hard_topics) or 'none'}")
    if ctx.llm.live:
        raw, call = ctx.llm.complete_json(agent="compliance", instructions=instructions, input_text=input_text,
                                          meter=ctx.meter, max_output_tokens=4000)
        verdict = "pass" if str(raw.get("verdict", "")).strip().lower() == "pass" else "flag"
        issues = [str(i)[:200] for i in (raw.get("issues") or []) if str(i).strip()][:6]
        review = {"verdict": verdict, "issues": issues, "source": "gpt"}
    else:
        review = {"verdict": "pass", "issues": [], "source": "mock (deterministic checks only)"}
        call = ctx.llm.record_estimate(ctx.meter, "compliance", instructions, input_text, review)
    return review, call
