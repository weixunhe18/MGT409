"""Responses API parsing, fail-closed on incomplete responses, and .env parsing. No network."""

import tempfile
import unittest
from pathlib import Path

from supplier_agent.config import DEFAULT_PRICES, _parse_env_file
from supplier_agent.llm import LLMError, Meter, PortkeyLLM, cost_usd, extract_output_text, parse_usage

RESPONSE = {
    "id": "resp_1",
    "status": "completed",
    "output": [
        {"type": "reasoning", "summary": []},
        {"type": "message", "role": "assistant",
         "content": [{"type": "output_text", "text": "{\"verdict\": \"pass\", \"issues\": []}"}]},
    ],
    "usage": {"input_tokens": 1500, "input_tokens_details": {"cached_tokens": 1024},
              "output_tokens": 300, "output_tokens_details": {"reasoning_tokens": 250}},
}


class FakePortkey(PortkeyLLM):
    def __init__(self, response):
        super().__init__("test-key")
        self.response = response
        self.payloads = []

    def _post(self, payload):
        self.payloads.append(payload)
        return self.response


class ResponsesApiTests(unittest.TestCase):
    def meter(self):
        return Meter(prices=dict(DEFAULT_PRICES))

    def test_parses_text_and_usage(self):
        self.assertIn("verdict", extract_output_text(RESPONSE))
        self.assertEqual(parse_usage(RESPONSE), (1500, 1024, 300))

    def test_cost_formula_matches_lecture_11(self):
        # 476 uncached * $0.10 + 1024 cached * $0.01 + 300 out * $0.50, per 1M tokens
        self.assertAlmostEqual(cost_usd(DEFAULT_PRICES, 1500, 1024, 300), (47.6 + 10.24 + 150) / 1_000_000)

    def test_complete_json_records_real_usage(self):
        llm, meter = FakePortkey(RESPONSE), self.meter()
        data, call = llm.complete_json(agent="compliance", instructions="i", input_text="x", meter=meter)
        self.assertEqual(data["verdict"], "pass")
        self.assertEqual(call["cached_tokens"], 1024)
        self.assertFalse(call["estimated"])
        self.assertEqual(llm.payloads[0]["model"], "gpt-6-luna")
        self.assertEqual(llm.payloads[0]["text"], {"format": {"type": "json_object"}})

    def test_reasoning_and_cache_write_tokens_are_recorded_and_billed(self):
        usage = {"input_tokens": 1500, "input_tokens_details": {"cached_tokens": 1024, "cache_write_tokens": 100},
                 "output_tokens": 300, "output_tokens_details": {"reasoning_tokens": 250}}
        llm, meter = FakePortkey(dict(RESPONSE, usage=usage)), self.meter()
        _, call = llm.complete_json(agent="context", instructions="i", input_text="x", meter=meter)
        self.assertEqual(call["reasoning_tokens"], 250)
        self.assertEqual(call["cache_write_tokens"], 100)
        self.assertAlmostEqual(call["cost_usd"], cost_usd(DEFAULT_PRICES, 1500, 1024, 300, 100), places=8)

    def test_portkey_cache_refresh_option_sets_the_force_refresh_header(self):
        self.assertEqual(PortkeyLLM("k", cache="refresh").extra_headers, {"x-portkey-cache-force-refresh": "true"})
        self.assertEqual(PortkeyLLM("k").extra_headers, {})

    def test_incomplete_response_fails_closed_but_is_still_billed(self):
        partial = dict(RESPONSE, status="incomplete", incomplete_details={"reason": "max_output_tokens"})
        llm, meter = FakePortkey(partial), self.meter()
        with self.assertRaises(LLMError):
            llm.complete_json(agent="drafter", instructions="i", input_text="x", meter=meter)
        self.assertEqual(len(meter.calls), 1)

    def test_non_json_output_fails_closed(self):
        bad = dict(RESPONSE, output=[{"type": "message", "content": [{"type": "output_text", "text": "sure!"}]}])
        with self.assertRaises(LLMError):
            FakePortkey(bad).complete_json(agent="manager", instructions="i", input_text="x", meter=self.meter())


class EnvFileTests(unittest.TestCase):
    def parse(self, content, encoding):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_bytes(content.encode(encoding))
            return _parse_env_file(path)

    def test_utf8_with_comments_and_quotes(self):
        env = self.parse('# comment\nPORTKEY_API_KEY="abc123"\nMODEL_NAME=gpt-6-luna # inline\n', "utf-8")
        self.assertEqual(env["PORTKEY_API_KEY"], "abc123")
        self.assertEqual(env["MODEL_NAME"], "gpt-6-luna")

    def test_utf16_written_by_windows_powershell(self):
        env = self.parse("﻿PORTKEY_API_KEY=abc123\r\n", "utf-16-le")
        self.assertEqual(env["PORTKEY_API_KEY"], "abc123")


if __name__ == "__main__":
    unittest.main()
