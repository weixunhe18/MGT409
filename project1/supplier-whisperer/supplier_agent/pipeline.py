"""The pipeline: webhook event -> guardrails -> manager -> context -> drafter -> compliance -> decision.

Orchestration is plain code, not an LLM. A model can never skip the compliance step, pick a
recipient, attach a file, or loosen a hard rule. Every step is written to a trace the UI shows.
"""

from __future__ import annotations

import re
import threading
import time
import traceback
from datetime import datetime
from datetime import time as dtime

from .agents import AgentContext, run_compliance_review, run_context, run_drafter, run_manager
from .config import AppConfig
from .guardrails import (TOPIC_LABELS, check_outbound, check_sender, domain_of, is_auto_reply, scan_html,
                         scan_injection, strip_quoted)
from .knowledge import KnowledgeBase
from .llm import BudgetExceeded, LLMError, Meter, MockLLM
from .store import Store, now_iso
from .webhook import normalize_event

OUTCOMES = {
    "AUTO_SENT": "Sent by agent",
    "NEEDS_APPROVAL": "Draft awaiting you",
    "ESCALATED": "Needs your decision",
    "QUARANTINED": "Quarantined (prompt injection)",
    "BLOCKED": "Blocked sender",
    "HELD": "Held (no reply)",
    "FYI": "No reply needed",
}
RISK_LEVELS = ("low", "medium", "high")
SCHEDULE_MODES = ("clock", "autonomous", "supervised")
MIN_CONFIDENCE = {"low": 2.0, "medium": 0.75, "high": 0.6}


class Trace:
    def __init__(self) -> None:
        self.steps: list[dict] = []
        self._t = time.perf_counter()

    def add(self, key: str, title: str, status: str, detail: str, call: dict | None = None,
            data: dict | None = None) -> None:
        now = time.perf_counter()
        step = {"key": key, "title": title, "status": status, "detail": detail,
                "ms": int((now - self._t) * 1000)}
        self._t = now
        if call:
            step["usage"] = {k: call.get(k) for k in
                             ("model", "input_tokens", "cached_tokens", "output_tokens", "cost_usd", "ms", "estimated",
                              "gateway_cache") if k in call}
        if data is not None:
            step["data"] = data
        self.steps.append(step)


def _hhmm(value: str, default: str) -> dtime:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return datetime.strptime(default, "%H:%M").time()


def reply_subject(subject: str) -> str:
    subject = (subject or "").strip()
    if re.match(r"^\s*(re|回复|答复)\s*[:：]", subject, re.I):
        return subject
    return f"Re: {subject}"


def _usage_brief(call: dict | None) -> str:
    if not call:
        return ""
    tag = "est. " if call.get("estimated") else ""
    return (f" [{tag}{call['input_tokens']} in / {call['cached_tokens']} cached / {call['output_tokens']} out, "
            f"${call['cost_usd']:.5f}]")


class Pipeline:
    def __init__(self, *, store: Store, kb: KnowledgeBase, policy: dict, config: AppConfig, live_llm=None):
        self.store = store
        self.kb = kb
        self.policy = policy
        self.config = config
        self.mock_llm = MockLLM()
        self.live_llm = live_llm
        self.sensitive_terms = kb.sensitive_terms(policy.get("sensitive_terms"))
        self.shareable_text = kb.shareable_text()
        self.own_domain = domain_of(str(policy.get("owner", {}).get("inbox", "")))
        self._human_lock = threading.Lock()
        # Extra allowlist entries that apply only when a real mailbox is connected (e.g. "@yale.edu").
        self.mailbox_allow: list[str] = []

    # ------------------------------------------------------------- settings
    @property
    def owner_first(self) -> str:
        owner = self.policy.get("owner", {})
        return owner.get("first_name") or (owner.get("name") or "the engineer").split()[0]

    def settings(self) -> dict:
        s = dict(self.policy.get("defaults", {}))
        s.setdefault("extra_allow", [])
        s.setdefault("extra_block", [])
        s.update(self.store.get_settings())
        if s.get("risk_tolerance") not in RISK_LEVELS:
            s["risk_tolerance"] = "medium"
        if s.get("schedule_mode") not in SCHEDULE_MODES:
            s["schedule_mode"] = "clock"
        mode = str(s.get("llm_mode", "auto")).lower()
        if self.config.llm_mode in ("live", "mock") and mode == "auto":
            mode = self.config.llm_mode
        if mode not in ("live", "mock"):
            mode = "live" if self.live_llm else "mock"
        if mode == "live" and not self.live_llm:
            mode = "mock"
        s["llm_mode"] = mode
        try:
            s["daily_budget_usd"] = max(0.0, float(s.get("daily_budget_usd", 1.0)))
        except (TypeError, ValueError):
            s["daily_budget_usd"] = 1.0
        s["paused"] = bool(s.get("paused", False))
        return s

    def schedule_state(self, settings: dict, now: datetime | None = None) -> tuple[bool, str]:
        mode = settings.get("schedule_mode", "clock")
        if mode == "autonomous":
            return True, "Night mode (set manually): agent may send low-risk replies"
        if mode == "supervised":
            return False, "Day mode (set manually): every reply waits for you"
        hours = self.policy.get("supervised_hours", {})
        now = now or datetime.now()
        start, end = _hhmm(hours.get("start"), "09:00"), _hhmm(hours.get("end"), "17:00")
        in_hours = now.weekday() in hours.get("days", [0, 1, 2, 3, 4]) and start <= now.time() < end
        if in_hours:
            return False, f"Business hours ({start:%H:%M}-{end:%H:%M}): {self.owner_first} is online, so replies wait for approval"
        return True, "Off hours: autonomous mode"

    # --------------------------------------------------------------- process
    def process(self, event: dict, *, signature_note: str = "signature verified") -> dict:
        email = normalize_event(event)
        # Demo threads start the way real ones do: with Wei's own email to the supplier (thread memory only).
        for prior in event.get("_prior_outbound") or []:
            self.store.add_history(email["thread_id"], email["from_addr"], str(prior.get("subject", "")),
                                   str(prior.get("text", "")), str(prior.get("sent_at", "")),
                                   str(prior.get("message_id", "")))
        return self.process_email(email, signature_note=signature_note)

    def process_email(self, email: dict, *, signature_note: str = "signature verified", run_id: int | None = None,
                      override_injection: bool = False) -> dict:
        t0 = time.perf_counter()
        if run_id is None and self.store.has_message(email["message_id"]):
            return {"outcome": "DUPLICATE", "message_id": email["message_id"],
                    "headline": "Duplicate delivery ignored (webhook retry)"}
        settings = self.settings()
        autonomous, schedule_label = self.schedule_state(settings)
        limits = self.policy.get("limits", {})
        trace = Trace()
        trace.add("webhook", "Webhook received", "ok",
                  f"{email.get('event_type') or 'message.received'} for thread {email['thread_id']} · {signature_note}")
        run: dict = {
            "email": email,
            "received_at": now_iso(),
            "llm_mode": settings["llm_mode"],
            "model": self.live_llm.model if settings["llm_mode"] == "live" and self.live_llm else self.mock_llm.model,
            "settings_snapshot": {"risk_tolerance": settings["risk_tolerance"], "autonomous": autonomous,
                                  "schedule": schedule_label, "llm_mode": settings["llm_mode"]},
            "trace": trace.steps,
            "draft": None,
            "human_status": "n/a",
            "send_now": False,
        }
        meter = Meter(
            prices=self.config.prices,
            max_calls=int(limits.get("max_llm_calls_per_email", 6)),
            per_email_budget_usd=float(limits.get("per_email_budget_usd", 0.05)),
            daily_spent_usd=self.store.spend_today()["cost_usd"],
            daily_budget_usd=settings["daily_budget_usd"],
        )
        try:
            self._run(run, email, settings, trace, meter, autonomous, schedule_label, override_injection)
        except BudgetExceeded as exc:
            trace.add("budget", "Budget guard", "stop", str(exc))
            self._finish(run, "HELD", f"Budget guard stopped the agent before it could overspend: {exc}", ["budget"])
        except LLMError as exc:
            trace.add("error", "Model error", "stop", str(exc)[:400])
            self._finish(run, "ESCALATED",
                         f"Model error, so the agent stopped and handed this to {self.owner_first} (fail closed).",
                         ["llm_error"])
        except Exception as exc:  # noqa: BLE001  fail closed on anything unexpected
            trace.add("error", "Unexpected error", "stop", f"{type(exc).__name__}: {exc}")
            run["error_traceback"] = traceback.format_exc()[-2000:]
            self._finish(run, "ESCALATED",
                         f"Unexpected error, so nothing was sent and {self.owner_first} must handle it (fail closed).",
                         ["error"])
        run["usage"] = meter.totals()
        run["calls"] = meter.calls
        if run_id is not None:  # re-runs add to (never replace) what this email already cost
            previous = self.store.get_run(run_id) or {}
            for key in ("input_tokens", "cached_tokens", "output_tokens"):
                run["usage"][key] += int(previous.get(key) or 0)
            run["usage"]["cost_usd"] = round(run["usage"]["cost_usd"] + float(previous.get("cost_usd") or 0), 6)
            run["usage"]["includes_earlier_attempts"] = True
        run["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        draft = run.get("draft")
        if run.get("send_now") and draft:
            # Last-moment check: the kill switch or Day mode may have changed while the models were working.
            latest = self.settings()
            still_autonomous, _ = self.schedule_state(latest)
            if latest["paused"] or not still_autonomous:
                trace.add("last_check", "Last-moment check", "stop",
                          "The agent was paused (or Day mode started) while this email was being processed, "
                          "so the reply was NOT sent.")
                if run["outcome"] == "AUTO_SENT":
                    self._finish(run, "NEEDS_APPROVAL", "Draft ready. Not sent: the agent was paused or Day mode "
                                                        "started mid-run.", ["paused_mid_run"])
                else:
                    run["send_now"] = False
        if run["outcome"] in ("NEEDS_APPROVAL", "ESCALATED"):
            run["human_status"] = "pending"
        if run.get("send_now") and draft:
            run["sent"] = {"by": "agent", "at": now_iso()}
        saved_id = self.store.save_run(run, run_id=run_id)
        run["id"] = saved_id
        if run.get("sent") and draft:
            self.store.add_outbox(saved_id, email["thread_id"], draft["to"][0], draft["subject"], draft["body"], "agent")
        return run

    # ------------------------------------------------------------------ core
    def _finish(self, run: dict, outcome: str, headline: str, tags: list[str], send: bool = False) -> None:
        run["outcome"] = outcome
        run["outcome_label"] = OUTCOMES.get(outcome, outcome)
        run["headline"] = headline
        run["tags"] = tags
        run["send_now"] = bool(send)

    def _run(self, run, email, settings, trace, meter, autonomous, schedule_label, override_injection) -> None:
        first = self.owner_first

        if settings["paused"]:
            trace.add("kill_switch", "Kill switch", "stop",
                      f"{first} paused the agent. No model reads this email and nothing is sent.")
            return self._finish(run, "HELD", "Agent paused (kill switch). Waiting for you.", ["paused"])

        if is_auto_reply(email.get("subject", ""), email.get("headers")):
            trace.add("loop_guard", "Loop guard", "stop", "Auto-reply or out-of-office detected. Never answer a robot.")
            return self._finish(run, "FYI", "Automatic reply detected, so no response (prevents email ping-pong).",
                                ["auto_reply"])

        # 1. Sender gate: before any model sees anything.
        sender = check_sender(email.get("from_raw", ""), self.policy,
                              list(settings.get("extra_allow") or []) + self.mailbox_allow, settings.get("extra_block"))
        auth = email.get("auth")
        if sender["status"] == "allowed" and isinstance(auth, dict) and not auth.get("verified"):
            # Real mail: anyone can type an allowlisted From line, so trust it only with DKIM/DMARC.
            sender = {**sender, "status": "unknown", "contact": None,
                      "reason": "Sender is allowlisted, but the message failed DKIM/DMARC, so it may be forged."}
        run["sender"] = sender
        if sender["status"] == "blocked":
            trace.add("sender", "Sender check", "stop", sender["reason"])
            return self._finish(run, "BLOCKED", f"Blocklisted sender {sender['address']}. Dropped, no reply.",
                                ["blocklist"])
        if sender["status"] == "impersonation":
            trace.add("sender", "Sender check", "stop", sender["reason"] + " Security alert raised.")
            return self._finish(run, "BLOCKED", f"Possible impersonation: {sender['reason']} No reply, alert raised.",
                                ["impersonation", "security_alert"])
        if sender["status"] == "unknown":
            trace.add("sender", "Sender check", "stop", sender["reason"] + " No model call, no reply.")
            return self._finish(run, "HELD", f"{sender['address']} is not on the allowlist. Held for you, no tokens spent.",
                                ["unknown_sender"])
        company = (sender.get("contact") or {}).get("company") or "allowlisted"
        trace.add("sender", "Sender check", "ok", f"{sender['address']} is on the allowlist ({company}).")

        # 2. Visible text only; hidden HTML never reaches a model.
        html_visible = scan_html(email["html"])["visible_text"] if email.get("html") else ""
        source_text = email.get("text") if (email.get("text") or "").strip() else html_visible
        email["visible_text"] = strip_quoted(source_text or "")

        # 3. Prompt-injection scan.
        inj = scan_injection(email.get("text", ""), email.get("html"), domain_of(sender["address"]), self.own_domain,
                             float(self.policy.get("suspicious_threshold", 0.4)),
                             float(self.policy.get("injection_threshold", 1.0)))
        armor = email.get("agent_armor")
        if isinstance(armor, dict) and str(armor.get("verdict", "")).lower() == "review":
            inj["signals"].append({"signal": "agentmail_agent_armor", "weight": 0.6, "evidence": "AgentMail verdict: review"})
            inj["score"] = round(inj["score"] + 0.6, 2)
            if inj["verdict"] == "clean":
                inj["verdict"] = "suspicious"
        run["injection"] = inj
        threshold = float(self.policy.get("injection_threshold", 1.0))
        top = ", ".join(s["signal"] for s in inj["signals"][:4]) or "no signals"
        if inj["verdict"] == "injection" and not override_injection:
            trace.add("injection", "Prompt-injection scan", "stop",
                      f"Score {inj['score']} ≥ {threshold}: {top}. Email quarantined before any model saw it.",
                      data={"signals": inj["signals"], "hidden_text": inj["hidden_text"]})
            evidence = inj["hidden_text"] or (inj["signals"][0]["evidence"] if inj["signals"] else "")
            return self._finish(run, "QUARANTINED",
                                f"Prompt injection blocked (score {inj['score']}): \"{evidence[:110]}…\"",
                                ["prompt_injection", "security_alert"])
        if override_injection:
            trace.add("injection", "Prompt-injection scan", "warn",
                      f"Score {inj['score']} ({top}). {first} released this email; hidden text is still stripped "
                      "and the reply will wait for approval.", data={"signals": inj["signals"]})
        else:
            trace.add("injection", "Prompt-injection scan", "warn" if inj["verdict"] == "suspicious" else "ok",
                      f"Score {inj['score']} ({inj['verdict']}): {top}.", data={"signals": inj["signals"]})

        # 4. Budget pre-check and thread memory.
        if meter.daily_spent_usd >= meter.daily_budget_usd:
            raise BudgetExceeded(f"daily budget ${meter.daily_budget_usd:.2f} already used today")
        thread = self.store.thread_history(email["thread_id"], before_message_id=email["message_id"])
        trace.add("memory", "Thread memory", "ok" if thread else "info",
                  f"Loaded {len(thread)} earlier message(s) from this conversation." if thread
                  else "New conversation (no earlier messages).")

        llm = self.live_llm if settings["llm_mode"] == "live" and self.live_llm else self.mock_llm
        ctx = AgentContext(email=email, kb=self.kb, policy=self.policy, llm=llm, meter=meter, thread=thread)

        # 5. Manager: triage.
        triage, call = run_manager(ctx)
        run["triage"] = triage
        n_q = len(triage["questions"])
        hard_labels = ", ".join(TOPIC_LABELS[t] for t in triage["hard_topics"])
        trace.add("manager", "Manager agent: triage", "warn" if triage["hard_topics"] else "ok",
                  f"Intent: {triage['intent']}. {n_q} question(s)."
                  + (f" Needs {first}: {hard_labels}." if hard_labels else " No commitment topics.")
                  + _usage_brief(call),
                  call, data={"summary": triage["summary"], "questions": triage["questions"],
                              "topic_evidence": triage.get("topic_evidence", {})})
        if not triage["questions"] and not triage["hard_topics"] and not triage.get("reply_needed", True):
            return self._finish(run, "FYI", f"FYI only: {triage['summary'][:120]}", ["fyi"])

        # 6. Internal context: answer from SHAREABLE spec only.
        answers, call = run_context(ctx, triage["questions"])
        run["answers"] = {str(k): v for k, v in answers.items()}
        if call is None:
            trace.add("context", "Internal context agent", "skip",
                      f"Every question needs {first}'s decision, so no spec lookup (saves tokens).")
        else:
            answered = sum(1 for a in answers.values() if a["answerable"])
            ungrounded = sum(1 for a in answers.values() if a.get("grounded") is False)
            trace.add("context", "Internal context agent: spec Q&A", "ok" if answered == len(answers) else "warn",
                      f"Answered {answered}/{len(answers)} from shareable spec sections."
                      + (f" {ungrounded} answer(s) had numbers not in the spec." if ungrounded else
                         " All numbers found in the spec.") + _usage_brief(call),
                      call, data={"answers": run["answers"]})

        # 7. Email agent: draft. Recipients, subject and attachments are set by code, not the model.
        body, call = run_drafter(ctx, triage, answers)
        draft = {"to": [sender["address"]], "cc": [], "subject": reply_subject(email.get("subject", "")),
                 "body": body, "attachments": []}
        run["draft"] = draft
        trace.add("drafter", "Email agent: draft reply", "ok",
                  f"Drafted {len(body.split())} words to {sender['address']} (recipient locked by code)."
                  + _usage_brief(call), call)

        # 8. Compliance: deterministic checks + LLM second opinion (LLM can only make it stricter).
        det = check_outbound(body, to=draft["to"], cc=draft["cc"], attachments=draft["attachments"],
                             original_sender=sender["address"], sensitive_terms=self.sensitive_terms,
                             shareable_text=self.shareable_text, signature=ctx.signature)
        review, call = run_compliance_review(ctx, body, triage["hard_topics"], answers)
        run["compliance"] = {"deterministic": det, "llm_review": review}
        passed = sum(1 for c in det["checks"] if c["ok"])
        status = "ok" if det["passed"] and review["verdict"] == "pass" else "warn" if det["passed"] else "stop"
        trace.add("compliance", "Compliance agent", status,
                  f"{passed}/{len(det['checks'])} hard checks passed; reviewer verdict: {review['verdict']}."
                  + (" Blocked: " + "; ".join(c["label"] for c in det["blocking"]) if det["blocking"] else "")
                  + _usage_brief(call),
                  call, data={"checks": det["checks"], "review": review})

        self._decide(run, email, settings, triage, answers, det, review, inj, override_injection, trace,
                     autonomous, schedule_label)

    def _decide(self, run, email, settings, triage, answers, det, review, inj, override_injection, trace,
                autonomous, schedule_label) -> None:
        first = self.owner_first
        risk = settings["risk_tolerance"]
        min_conf = MIN_CONFIDENCE.get(risk, 0.75)
        answered = [a for a in answers.values() if a.get("answerable")]
        open_count = sum(1 for q in triage["questions"]
                         if not q["topics"] and not answers.get(q["id"], {}).get("answerable"))
        soft: list[str] = []
        if triage.get("engineering_change"):
            soft.append("supplier proposed a part, material or process change")
        if inj["verdict"] == "suspicious":
            soft.append(f"injection scan score {inj['score']} (suspicious)")
        if override_injection:
            soft.append(f"quarantine released by {first}")
        if triage.get("suspicious_instructions"):
            soft.append("manager agent saw text aimed at the AI")
        if review.get("verdict") == "flag":
            soft.append("compliance reviewer flagged: " + "; ".join(review.get("issues", [])[:2]))
        if any(a.get("grounded") is False for a in answered):
            soft.append("an answer contains numbers not found in the spec")
        low_conf = [a for a in answered if a.get("confidence", 0) < min_conf]
        if low_conf and risk != "low":
            soft.append(f"{len(low_conf)} answer(s) below {min_conf:.2f} confidence")
        max_replies = int(self.policy.get("limits", {}).get("max_agent_replies_per_thread_per_day", 3))
        replies = self.store.agent_replies_in_thread(email["thread_id"])
        if replies >= max_replies:
            soft.append(f"loop guard: agent already replied {replies} times in this thread today")

        def done(outcome, headline, tags, send=False, status="ok"):
            self._finish(run, outcome, headline, tags, send)
            trace.add("decision", "Decision", status, f"{headline} (risk: {risk}; {schedule_label})")

        if not det["passed"]:
            why = "; ".join(f"{c['label']} ({c['detail']})" if c["detail"] else c["label"] for c in det["blocking"])
            return done("ESCALATED", f"Compliance blocked the draft: {why}. Nothing sent.",
                        ["compliance_block"], status="stop")
        if triage["hard_topics"]:
            labels = ", ".join(TOPIC_LABELS[t] for t in triage["hard_topics"])
            # "Are you a bot?" never gets an automatic reply, not even a holding one: Wei answers that personally.
            # At Medium and High the supplier gets a no-commitment holding reply so they know Wei is on it,
            # but only if they asked or requested something: never in answer to a pure status update.
            asked = triage.get("supplier_asked", True)
            holding_ok = (autonomous and risk in ("medium", "high") and not soft and asked
                          and "identity" not in triage["hard_topics"])
            note = ("Holding reply sent (no commitments)." if holding_ok else
                    "Holding reply drafted for your approval." if asked else
                    "No question was asked, so no holding reply was sent; a draft is ready if you want one.")
            return done("ESCALATED", f"{labels[0].upper() + labels[1:]}: needs your decision. {note}",
                        ["commitment"] + list(triage["hard_topics"]), send=holding_ok, status="warn")
        if soft:
            return done("NEEDS_APPROVAL", "Draft ready for review: " + "; ".join(soft[:2]) +
                        (f"; {open_count} open item(s)" if open_count else "") + ".", ["review"], status="warn")
        if open_count:
            if autonomous and risk == "high":
                return done("AUTO_SENT", f"Answered {len(answered)} question(s); {open_count} open item(s) flagged "
                                         f"for {first} in the reply.", ["auto"], send=True)
            return done("NEEDS_APPROVAL", f"Draft ready: answered {len(answered)}, {open_count} open item(s) need "
                                          "your input.", ["open_items"], status="warn")
        if not autonomous:
            return done("NEEDS_APPROVAL", f"Draft ready ({len(answered)} answers). {schedule_label}.",
                        ["supervised"], status="warn")
        if risk == "low":
            return done("NEEDS_APPROVAL", f"Draft ready ({len(answered)} answers). Risk tolerance is Low, "
                                          "so you approve every reply.", ["risk_low"], status="warn")
        return done("AUTO_SENT", f"Answered {len(answered)} technical question(s) from the spec and sent the reply.",
                    ["auto"], send=True)

    # -------------------------------------------------------- human actions
    def approve(self, run_id: int, body: str | None = None, force: bool = False) -> dict:
        with self._human_lock:  # check-then-send must be atomic (double clicks, parallel requests)
            row = self.store.get_run(run_id)
            if not row:
                return {"ok": False, "error": "Run not found."}
            result = row["result"]
            draft = result.get("draft")
            if not draft:
                return {"ok": False, "error": "This email has no draft to send."}
            if result.get("sent"):
                return {"ok": False, "error": "A reply was already sent for this email."}
            if result.get("human_status") == "reprocessing":
                return {"ok": False, "error": "This email is being re-run. Try again in a moment."}
            text = body if (body is not None and body.strip()) else draft["body"]
            signature = str(self.policy.get("assistant_signature", ""))
            det = check_outbound(text, to=draft["to"], cc=draft.get("cc", []), attachments=[],
                                 original_sender=draft["to"][0], sensitive_terms=self.sensitive_terms,
                                 shareable_text=self.shareable_text, signature="")
            if not det["passed"] and not force:
                return {"ok": False, "needs_force": True, "blocking": det["blocking"]}
            draft["body"] = text
            result["draft"] = draft
            result["sent"] = {"by": "human", "at": now_iso(), "compliance_override": not det["passed"]}
            result["human_status"] = "approved"
            self.store.update_run_result(run_id, result)
            self.store.add_outbox(run_id, row["thread_id"], draft["to"][0], draft["subject"], text, "human")
            first_line = signature.splitlines()[0].lower() if signature.strip() else ""
            return {"ok": True, "signature_present": first_line in text.lower()}

    def set_human_status(self, run_id: int, status: str) -> dict:
        with self._human_lock:
            row = self.store.get_run(run_id)
            if not row:
                return {"ok": False, "error": "Run not found."}
            result = row["result"]
            result["human_status"] = status
            self.store.update_run_result(run_id, result)
            return {"ok": True}

    def reprocess(self, run_id: int, override_injection: bool = False) -> dict:
        with self._human_lock:
            row = self.store.get_run(run_id)
            if not row:
                return {"ok": False, "error": "Run not found."}
            result = row["result"]
            if result.get("sent") or result.get("human_status") in ("approved", "reprocessing"):
                return {"ok": False, "error": "A reply was already sent (or a re-run is running) for this email."}
            result["human_status"] = "reprocessing"
            self.store.update_run_result(run_id, result)
        try:
            run = self.process_email(row["email"], signature_note=f"re-run requested by {self.owner_first}",
                                     run_id=run_id, override_injection=override_injection)
        except Exception:
            self.set_human_status(run_id, "n/a")
            raise
        return {"ok": True, "outcome": run.get("outcome")}

    def update_sender_lists(self, address: str, action: str) -> dict:
        address = (address or "").strip().lower()
        if "@" not in address:
            return {"ok": False, "error": "Not an email address."}
        s = self.store.get_settings()
        allow = [a for a in s.get("extra_allow", []) if a != address]
        block = [a for a in s.get("extra_block", []) if a != address]
        if action == "allow":
            allow.append(address)
        elif action == "block":
            block.append(address)
        else:
            return {"ok": False, "error": "action must be allow or block"}
        self.store.set_settings({"extra_allow": allow, "extra_block": block})
        return {"ok": True}
