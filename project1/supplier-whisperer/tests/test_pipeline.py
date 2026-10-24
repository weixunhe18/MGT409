"""End-to-end pipeline tests on the sample inbox (mock engine + scripted fake models). No network, no key."""

import copy
import unittest
from pathlib import Path

from supplier_agent.config import DATA_DIR, AppConfig, load_policy, load_sample_events
from supplier_agent.knowledge import KnowledgeBase
from supplier_agent.llm import LLMError, MockLLM
from supplier_agent.pipeline import Pipeline
from supplier_agent.store import Store

SAMPLE = DATA_DIR / "sample"
POLICY = load_policy(SAMPLE)
KB = KnowledgeBase.load(SAMPLE / "product_spec.md")
EVENTS = load_sample_events(SAMPLE)
SIGNATURE = POLICY["assistant_signature"]
# Email 9: routine spec questions, the demo's auto-send case (emails 1 and 8 propose changes, so they wait).
ROUTINE = next(e for e in EVENTS if e["event_id"] == "evt_sample_09")


def make(live_llm=None, **settings):
    config = AppConfig(dataset_dir=SAMPLE, db_path=Path(":memory:"), llm_mode="mock")
    store = Store(":memory:")
    pipeline = Pipeline(store=store, kb=KB, policy=POLICY, config=config, live_llm=live_llm)
    store.set_settings({"risk_tolerance": "medium", "schedule_mode": "autonomous", **settings})
    return pipeline, store


def run_all(pipeline):
    return {e["event_id"]: pipeline.process(copy.deepcopy(e)) for e in EVENTS}


class SpyLLM(MockLLM):
    """Mock engine that records every prompt it would have sent to a model."""

    def __init__(self):
        super().__init__()
        self.prompts = []

    def record_estimate(self, meter, agent, instructions, input_text, output_obj):
        self.prompts.append(instructions + "\n" + input_text)
        return super().record_estimate(meter, agent, instructions, input_text, output_obj)


class ScriptedLLM:
    """A fake 'live' model whose outputs we control, including deliberately bad ones."""

    live = True
    model = "scripted-fake"

    def __init__(self, answer="Maximum 2.5 mm.", body=None, verdict="pass", fail=False):
        self.answer, self.body, self.verdict, self.fail = answer, body, verdict, fail

    def complete_json(self, *, agent, instructions, input_text, meter, max_output_tokens=4000):
        if self.fail:
            raise LLMError("simulated outage")
        meter.check_before_call(agent)
        call = meter.record(agent, 1200, 1000, 80, 5, False, self.model)
        if agent == "manager":
            return {"summary": "Wall thickness question", "intent": "technical_question",
                    "questions": [{"id": 1, "text": "What is the max wall thickness?", "topics": [],
                                   "engineering_change": False}],
                    "suspicious_instructions": False, "reply_needed": True}, call
        if agent == "context":
            return {"answers": [{"id": 1, "answerable": True, "answer": self.answer, "source": "Enclosure",
                                 "confidence": 0.95}]}, call
        if agent == "drafter":
            return {"body": self.body or f"Hi Kevin,\n\n1. {self.answer}\n\nBest regards,\n{SIGNATURE}"}, call
        return {"verdict": self.verdict, "issues": [] if self.verdict == "pass" else ["sounds like a promise"]}, call


class PipelineTests(unittest.TestCase):
    def test_demo_inbox_matches_the_script(self):
        pipeline, store = make()
        runs = run_all(pipeline)
        for event in EVENTS:
            expected = event["_demo"]["expected"]
            self.assertEqual(runs[event["event_id"]]["outcome"], expected,
                             f"{event['event_id']}: {runs[event['event_id']].get('headline')}")
        self.assertEqual(len(store.list_outbox()), 3)  # email 9 answered + holding replies to emails 3 and 6

    def test_auto_sent_reply_is_locked_to_sender_and_compliant(self):
        pipeline, _ = make()
        run = run_all(pipeline)["evt_sample_09"]
        self.assertEqual(run["outcome"], "AUTO_SENT")
        self.assertEqual(run["draft"]["to"], ["kevin.zhang@hongyuan-mold.example"])
        self.assertEqual(run["draft"]["cc"], [])
        self.assertTrue(run["compliance"]["deterministic"]["passed"])
        self.assertIn("0.1 mm", run["draft"]["body"])
        self.assertTrue(run["draft"]["body"].rstrip().endswith(SIGNATURE))
        self.assertNotIn(" AI", run["draft"]["body"])  # persona signature, no "AI assistant" banner

    def test_are_you_a_bot_always_goes_to_wei(self):
        pipeline, store = make(risk_tolerance="high")  # even at the most trusting setting
        event = copy.deepcopy(EVENTS[0])
        event["message"]["message_id"] = "<identity@hongyuan-mold.example>"
        event["message"]["text"] = ("Hi John,\n\nQuick question before we continue: are you a real person or an AI? "
                                    "Your replies come very fast.\n\nThanks,\nKevin")
        run = pipeline.process(event)
        self.assertEqual(run["outcome"], "ESCALATED")
        self.assertIn("identity", run["triage"]["hard_topics"])
        self.assertFalse(run.get("sent"))
        self.assertEqual(store.list_outbox(), [])

    def test_low_risk_never_auto_sends(self):
        pipeline, store = make(risk_tolerance="low")
        outcomes = [r["outcome"] for r in run_all(pipeline).values()]
        self.assertNotIn("AUTO_SENT", outcomes)
        self.assertEqual(store.list_outbox(), [])

    def test_business_hours_never_auto_send(self):
        pipeline, store = make(schedule_mode="supervised")
        outcomes = [r["outcome"] for r in run_all(pipeline).values()]
        self.assertNotIn("AUTO_SENT", outcomes)
        self.assertEqual(store.list_outbox(), [])

    def test_medium_and_high_risk_send_holding_reply_without_commitments(self):
        for risk in ("medium", "high"):
            pipeline, _ = make(risk_tolerance=risk)
            run = run_all(pipeline)["evt_sample_03"]
            self.assertEqual(run["outcome"], "ESCALATED", risk)
            self.assertTrue(run.get("sent"), risk)
            for forbidden in ("4.20", "3.85", "20k", "Nov 15", "deposit"):
                self.assertNotIn(forbidden, run["draft"]["body"])

    def test_no_holding_reply_when_the_supplier_asked_nothing(self):
        pipeline, store = make()
        event = copy.deepcopy(ROUTINE)
        event["message"]["message_id"] = "<status@hongyuan-mold.example>"
        event["message"]["text"] = "Hi Wei,\n\nThe new quotation for 5000 pcs is in the system.\n\nKevin"
        run = pipeline.process(event)
        self.assertEqual(run["outcome"], "ESCALATED")  # Wei still has to see a quotation
        self.assertFalse(run.get("sent"))
        self.assertIn("No question was asked", run["headline"])
        self.assertEqual(store.list_outbox(), [])

    def test_threats_cost_zero_model_calls(self):
        pipeline, _ = make()
        runs = run_all(pipeline)
        for eid in ("evt_sample_04", "evt_sample_05", "evt_sample_07"):
            self.assertEqual(runs[eid]["usage"]["calls"], 0, eid)

    def test_confidential_spec_never_reaches_a_model(self):
        pipeline, _ = make()
        spy = SpyLLM()
        pipeline.mock_llm = spy
        run_all(pipeline)
        self.assertTrue(spy.prompts)
        terms = KB.sensitive_terms(POLICY["sensitive_terms"])
        for prompt in spy.prompts:
            low = prompt.lower()
            for term in terms:
                self.assertNotIn(term.lower(), low, f"'{term}' leaked into a prompt")
            self.assertNotIn("ignore all previous instructions", low)

    def test_duplicate_webhook_is_ignored(self):
        pipeline, store = make()
        self.assertEqual(pipeline.process(copy.deepcopy(ROUTINE))["outcome"], "AUTO_SENT")
        self.assertEqual(pipeline.process(copy.deepcopy(ROUTINE))["outcome"], "DUPLICATE")
        self.assertEqual(len(store.list_runs()), 1)
        self.assertEqual(len(store.list_outbox()), 1)

    def test_kill_switch_holds_everything(self):
        pipeline, store = make(paused=True)
        for run in run_all(pipeline).values():
            self.assertEqual(run["outcome"], "HELD")
            self.assertEqual(run["usage"]["calls"], 0)
        self.assertEqual(store.list_outbox(), [])

    def test_zero_budget_stops_before_any_model_call(self):
        pipeline, _ = make(daily_budget_usd=0.0)
        run = pipeline.process(copy.deepcopy(EVENTS[0]))
        self.assertEqual(run["outcome"], "HELD")
        self.assertIn("budget", run["tags"])
        self.assertEqual(run["usage"]["calls"], 0)

    def test_thread_memory_loads_earlier_messages(self):
        pipeline, _ = make()
        run = run_all(pipeline)["evt_sample_08"]
        memory = next(s for s in run["trace"] if s["key"] == "memory")
        # Wei's opening email + Kevin's email 1 (its reply waits for approval, so nothing sent yet)
        self.assertIn("Loaded 2", memory["detail"])
        history = pipeline.store.thread_history(run["email"]["thread_id"])
        self.assertTrue(history[0]["from"].startswith("Wei"))
        self.assertNotIn("wei", [o["sent_by"] for o in pipeline.store.list_outbox()])  # not shown as "sent"

    def test_loop_guard_stops_endless_auto_replies(self):
        pipeline, _ = make()
        outcomes = []
        for i in range(4):
            event = copy.deepcopy(ROUTINE)
            event["message"]["message_id"] = f"<loop-{i}@hongyuan-mold.example>"
            outcomes.append(pipeline.process(event)["outcome"])
        self.assertEqual(outcomes[:3], ["AUTO_SENT"] * 3)
        self.assertEqual(outcomes[3], "NEEDS_APPROVAL")

    def test_rogue_model_commitment_is_blocked_by_code(self):
        rogue = ScriptedLLM(body="Hi Kevin,\n\nGood news: we accept USD 3.85 and will place the PO for 20k pcs "
                                 "by Nov 15.\n\nBest regards,\n" + SIGNATURE)
        pipeline, store = make(live_llm=rogue, llm_mode="live", risk_tolerance="high")
        run = pipeline.process(copy.deepcopy(EVENTS[0]))
        self.assertEqual(run["outcome"], "ESCALATED")
        self.assertIn("compliance_block", run["tags"])
        self.assertEqual(store.list_outbox(), [])

    def test_invented_number_is_not_auto_sent(self):
        pipeline, store = make(live_llm=ScriptedLLM(answer="Maximum wall thickness is 2.9 mm."), llm_mode="live")
        run = pipeline.process(copy.deepcopy(ROUTINE))
        self.assertEqual(run["outcome"], "NEEDS_APPROVAL")
        self.assertFalse(run["answers"]["1"]["grounded"])
        self.assertEqual(store.list_outbox(), [])

    def test_reviewer_flag_downgrades_to_approval(self):
        pipeline, _ = make(live_llm=ScriptedLLM(verdict="flag"), llm_mode="live")
        self.assertEqual(pipeline.process(copy.deepcopy(ROUTINE))["outcome"], "NEEDS_APPROVAL")

    def test_live_happy_path_auto_sends_and_counts_cached_tokens(self):
        pipeline, store = make(live_llm=ScriptedLLM(), llm_mode="live")
        run = pipeline.process(copy.deepcopy(ROUTINE))
        self.assertEqual(run["outcome"], "AUTO_SENT")
        self.assertEqual(run["usage"]["calls"], 4)
        self.assertEqual(run["usage"]["cached_tokens"], 4000)
        self.assertFalse(run["usage"]["estimated"])

    def test_model_outage_fails_closed(self):
        pipeline, store = make(live_llm=ScriptedLLM(fail=True), llm_mode="live")
        run = pipeline.process(copy.deepcopy(EVENTS[0]))
        self.assertEqual(run["outcome"], "ESCALATED")
        self.assertIn("llm_error", run["tags"])
        self.assertEqual(store.list_outbox(), [])

    def test_kill_switch_pressed_mid_run_stops_the_send(self):
        class PausingLLM(ScriptedLLM):
            store = None

            def complete_json(self, *, agent, **kwargs):
                if agent == "compliance":
                    self.store.set_settings({"paused": True})  # Wei hits pause while the models are working
                return super().complete_json(agent=agent, **kwargs)

        llm = PausingLLM()
        pipeline, store = make(live_llm=llm, llm_mode="live")
        llm.store = store
        run = pipeline.process(copy.deepcopy(ROUTINE))
        self.assertEqual(run["outcome"], "NEEDS_APPROVAL")
        self.assertFalse(run.get("sent"))
        self.assertEqual(store.list_outbox(), [])

    def test_double_approve_sends_once(self):
        pipeline, store = make()
        run = run_all(pipeline)["evt_sample_02"]
        self.assertTrue(pipeline.approve(run["id"])["ok"])
        self.assertFalse(pipeline.approve(run["id"])["ok"])
        self.assertEqual(sum(1 for m in store.list_outbox() if m["run_id"] == run["id"]), 1)

    def test_rerun_refuses_sent_email_and_adds_cost(self):
        pipeline, store = make()
        runs = run_all(pipeline)
        self.assertFalse(pipeline.reprocess(runs["evt_sample_09"]["id"])["ok"])  # already auto-sent
        held = runs["evt_sample_05"]
        pipeline.update_sender_lists("david.li@quicktek-sourcing.example", "allow")
        before = store.get_run(runs["evt_sample_02"]["id"])["cost_usd"]
        self.assertTrue(pipeline.reprocess(runs["evt_sample_02"]["id"])["ok"])
        self.assertGreater(store.get_run(runs["evt_sample_02"]["id"])["cost_usd"], before)
        self.assertTrue(pipeline.reprocess(held["id"])["ok"])
        self.assertNotEqual(store.get_run(held["id"])["outcome"], "HELD")

    def test_reset_clears_everything_and_restarts_ids(self):
        pipeline, store = make()
        run_all(pipeline)
        store.reset()
        self.assertEqual(store.list_runs(), [])
        self.assertEqual(store.list_outbox(), [])
        self.assertEqual(pipeline.process(copy.deepcopy(EVENTS[0]))["id"], 1)

    def test_reviewer_gets_the_spec_line_behind_short_answers(self):
        from supplier_agent.agents import _spec_lines_for
        self.assertEqual(_spec_lines_for(KB, "0.1 mm maximum."),
                         ["Gate location and vestige: no gates on A-surfaces; gate vestige 0.1 mm maximum."])
        lines = _spec_lines_for(KB, "SPI-C1.")
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("Texture:"))  # not every line that merely contains a "1"

    def test_human_approval_sends_and_flags_risky_edits(self):
        pipeline, store = make(risk_tolerance="low")  # Low: the holding reply waits for Wei
        run = run_all(pipeline)["evt_sample_03"]
        risky = pipeline.approve(run["id"], body="Hi Jason, we accept USD 3.85.")
        self.assertTrue(risky.get("needs_force"))
        ok = pipeline.approve(run["id"], body="Hi Jason,\n\nThanks. Wei will reply on pricing directly.")
        self.assertTrue(ok["ok"])
        self.assertEqual(store.get_run(run["id"])["result"]["human_status"], "approved")


if __name__ == "__main__":
    unittest.main()
