"""Reconcile exported transactions and emails into an income-statement log."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


MODEL = "gpt-5.6-luna"
OUTPUT_NAME = "reconciliation_log.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def collect_evidence(docs_dir: Path, out_dir: Path) -> str:
    evidence: list[str] = []

    for path in sorted(out_dir.glob("*.json")):
        if path.name == OUTPUT_NAME:
            continue
        evidence.append(f"--- {path.name} ---\n{path.read_text(encoding='utf-8')}")

    emails_dir = docs_dir / "emails"
    for path in sorted(emails_dir.glob("*.txt")):
        evidence.append(f"--- {path.name} ---\n{path.read_text(encoding='utf-8')}")

    if not evidence:
        raise SystemExit("No output JSON or email files found for reconciliation")
    return "\n\n".join(evidence)


def parse_json_array(output_text: str) -> list[dict[str, Any]]:
    cleaned = output_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned).strip()
    value = json.loads(cleaned)
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError("LLM response was not a JSON array of objects")
    return value


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    required = (
        "id",
        "sources",
        "amounts_seen",
        "included_in_income_statement",
        "amount_used_in_income_statement",
        "resolution",
        "plain_english",
    )
    normalized = []
    for row in rows:
        missing = [field for field in required if field not in row]
        if missing:
            raise ValueError(f"Reconciliation row is missing fields: {missing}")
        if row["included_in_income_statement"] == "no":
            row["amount_used_in_income_statement"] = 0
        normalized.append(row)
    return normalized


def main() -> None:
    args = parse_args()
    if not args.docs_dir.is_dir():
        raise SystemExit(f"Documents directory does not exist: {args.docs_dir}")
    if not args.out_dir.is_dir():
        raise SystemExit(f"Output directory does not exist: {args.out_dir}")

    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")
    portkey_api_key = os.environ.get("PORTKEY_API_KEY")
    if not portkey_api_key:
        raise SystemExit("PORTKEY_API_KEY is missing from the root .env file")

    prompt_path = Path(__file__).resolve().parent / "prompts" / "reconcile.md"
    prompt = prompt_path.read_text(encoding="utf-8").replace(
        "{{evidence}}", collect_evidence(args.docs_dir, args.out_dir)
    )
    client = OpenAI(
        api_key=portkey_api_key,
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-provider": "openai"},
    )
    response = client.responses.create(
        model=MODEL,
        input=prompt,
        reasoning={"effort": "none"},
        max_output_tokens=4096,
    )
    rows = normalize_rows(parse_json_array(response.output_text))

    output_path = args.out_dir / OUTPUT_NAME
    output_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} reconciliation rows to {output_path}")


if __name__ == "__main__":
    main()
