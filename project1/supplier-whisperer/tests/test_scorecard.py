"""Supplier scorecard tests on synthetic conversations (the real threads it was calibrated on stay private)."""

import unittest
from datetime import datetime

from supplier_agent.scorecard import score


def convo(*items):
    return [{"role": r, "at": at, "text": t, "attachment": a} for r, at, t, a in items]


ASK = "1. What is the max wall thickness?\n2. Can you quote 1,000 pcs?"

# Replies in minutes, but passes everything to the factory and never delivers an answer.
FAST_BUT_VAGUE = convo(
    ("buyer", "2026-05-01 09:00", ASK, None),
    ("supplier", "2026-05-01 09:02", "ok", None),
    ("supplier", "2026-05-01 09:03", "I'll ask the factory", None),
    ("buyer", "2026-05-02 09:00", "Can you share the material datasheet?", None),
    ("supplier", "2026-05-02 09:05", "I don't know, I will check", None),
    ("buyer", "2026-05-06 09:00", "any update?", None),
    ("supplier", "2026-05-06 09:10", "factory hasn't replied yet", None),
)

# Replies the next morning, with numbers and documents.
SLOWER_BUT_KNOWLEDGEABLE = convo(
    ("buyer", "2026-05-01 09:00", ASK, None),
    ("supplier", "2026-05-01 21:00", "Max wall is 2.5 mm, core out bosses. 1,000 pcs quote attached in the PI.", "file"),
    ("buyer", "2026-05-02 09:00", "Can you share the material datasheet?", None),
    ("supplier", "2026-05-02 20:00", "Here is the ABS datasheet, UL94 V-0, 2.0 mm wall.", "file"),
)


class ScorecardTests(unittest.TestCase):
    def test_substance_beats_speed(self):
        fast, solid = score(FAST_BUT_VAGUE), score(SLOWER_BUT_KNOWLEDGEABLE)
        self.assertGreater(fast["subscores"]["speed"], solid["subscores"]["speed"])
        self.assertGreater(solid["overall"], fast["overall"])
        self.assertGreater(solid["subscores"]["knowledge"], fast["subscores"]["knowledge"])

    def test_counts_gaps_nudges_and_answers(self):
        s = score(FAST_BUT_VAGUE)
        self.assertEqual(s["knowledge_gaps"], 3)
        self.assertEqual(s["nudges_needed"], 1)
        self.assertEqual(s["questions_answered"], 0)
        self.assertEqual(score(SLOWER_BUT_KNOWLEDGEABLE)["questions_answered"], 2)

    def test_unanswered_question_counts_as_ghosted(self):
        s = score(convo(("buyer", "2026-05-01 09:00", "Can you quote this?", None),
                        ("supplier", "2026-05-08 09:00", "Sorry for late reply, price is $2.10 for 1,000 pcs", None)))
        self.assertEqual(s["ghosted"], 1)
        self.assertEqual(s["subscores"]["speed"], 20)

    def test_a_question_we_just_sent_is_not_ghosting(self):
        recent = convo(("buyer", "2026-05-01 09:00", "Can you quote this?", None))
        self.assertEqual(score(recent, now=datetime(2026, 5, 1, 10))["ghosted"], 0)
        self.assertEqual(score(recent, now=datetime(2026, 5, 9))["ghosted"], 1)

    def test_empty_conversation_is_neutral(self):
        self.assertEqual(score([])["questions_asked"], 0)


if __name__ == "__main__":
    unittest.main()
