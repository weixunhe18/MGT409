"""Spec-conflict check: supplier statements that contradict the spec (fictional TB-1 spec; no real data)."""

import copy
import unittest

from supplier_agent.conflicts import find_conflicts
from supplier_agent.scorecard import score
from tests.test_pipeline import KB, ROUTINE, make


class ConflictTests(unittest.TestCase):
    def details(self, text):
        return [c["detail"] for c in find_conflicts(text, KB)]

    def test_wrong_material_for_a_part(self):
        self.assertEqual(self.details("We will make the housing in ABS."), ["says ABS; spec says PC/ABS"])
        self.assertEqual(self.details("We will bond the lens with hot melt glue."),
                         ["says hot melt adhesive; spec says VHB tape"])

    def test_number_outside_the_spec(self):
        self.assertEqual(self.details("Main housing wall is 2.0mm, but near the screw boss some area is 2.8mm."),
                         ["2.8 mm is outside max 2.5 mm"])

    def test_matching_statements_and_proposals_are_not_conflicts(self):
        for text in ("Housing is PC/ABS, UL94 V-0.", "Snap fit interference is 0.3 mm.",
                     "Can we use an EPDM O-ring instead of silicone?",  # a question/proposal, not a claim
                     "To save cost, we could use EPDM instead of silicone.",  # names the spec material too
                     "For pilot tooling, can we use P20 steel?", "The weather is fine."):
            self.assertEqual(self.details(text), [], text)

    def test_matches_the_part_the_sentence_is_about(self):
        # "lens" must not pull in the housing material line, and vice versa.
        self.assertEqual(len(find_conflicts("The lens is bonded with hot melt glue.", KB)), 1)

    def test_conflict_gets_a_reconcile_question_even_without_a_question(self):
        pipeline, store = make()
        event = copy.deepcopy(ROUTINE)
        event["message"]["message_id"] = "<abs@hongyuan-mold.example>"
        event["message"]["text"] = "Hi Wei,\n\nFYI we will make the housing in ABS.\n\nKevin"
        run = pipeline.process(event)
        self.assertEqual(run["outcome"], "ESCALATED")
        self.assertIn("spec_conflict", run["tags"])
        self.assertTrue(run.get("sent"))
        body = run["draft"]["body"]
        self.assertIn("we will make the housing in ABS", body)
        self.assertIn("PC/ABS", body)
        self.assertIn("Which one is correct", body)

    def test_scorecard_counts_conflicts_against_knowledge(self):
        msgs = [{"role": "buyer", "at": "2026-05-01 09:00", "text": "What housing material?"},
                {"role": "supplier", "at": "2026-05-01 10:00", "text": "We will make the housing in ABS."}]
        with_kb, without = score(msgs, kb=KB), score(msgs)
        self.assertEqual(with_kb["spec_conflicts"], 1)
        self.assertLess(with_kb["subscores"]["knowledge"], without["subscores"]["knowledge"])


if __name__ == "__main__":
    unittest.main()
