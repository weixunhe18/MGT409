"""Extract bank-statement transaction lines into structured JSON rows."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader


MODEL = "gpt-5.6-luna"
TRANSACTION_RE = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+(?P<description>.+?)\s+(?P<amount>[+-]\d[\d,]*\.\d{2})$"
)
REQUIRED_FIELDS = (
    "date",
    "description",
    "amount",
    "classification",
    "credit_or_debit",
    "accounting_label",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def extract_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def find_transaction_lines(statement_text: str) -> list[str]:
    return [
        line.strip()
        for line in statement_text.splitlines()
        if TRANSACTION_RE.match(line.strip())
    ]


def load_prompt(prompt_path: Path, context: str, transaction_line: str) -> str:
    return (
        prompt_path.read_text(encoding="utf-8")
        .replace("{{statement_context}}", context)
        .replace("{{transaction_line}}", transaction_line)
    )


def parse_json_object(output_text: str) -> dict[str, Any]:
    cleaned = output_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned).strip()
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("LLM response was not a JSON object")
    return value


def normalize_row(value: dict[str, Any]) -> dict[str, Any]:
    missing = value.get("fields_not_found", [])
    if not isinstance(missing, list):
        missing = []
    missing = [str(field) for field in missing]
    row = {field: value.get(field) for field in REQUIRED_FIELDS}
    for field in REQUIRED_FIELDS:
        if row[field] is None and field not in missing:
            missing.append(field)
    row["fields_not_found"] = missing
    return row


def extract_transaction(client: OpenAI, prompt: str) -> dict[str, Any]:
    response = client.responses.create(
        model=MODEL,
        input=prompt,
        reasoning={"effort": "none"},
        max_output_tokens=512,
    )
    return parse_json_object(response.output_text)


def main() -> None:
    args = parse_args()
    if not args.docs_dir.is_dir():
        raise SystemExit(f"Documents directory does not exist: {args.docs_dir}")

    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")
    portkey_api_key = os.environ.get("PORTKEY_API_KEY")
    if not portkey_api_key:
        raise SystemExit("PORTKEY_API_KEY is missing from the root .env file")

    pdf_paths = sorted(args.docs_dir.rglob("bank_statement_jan2026.pdf"))
    if not pdf_paths:
        raise SystemExit(f"bank_statement_jan2026.pdf not found in {args.docs_dir}")
    pdf_path = pdf_paths[0]
    statement_text = extract_pdf_text(pdf_path)
    transaction_lines = find_transaction_lines(statement_text)
    if not transaction_lines:
        raise SystemExit(f"No transaction lines found in {pdf_path}")

    prompt_path = Path(__file__).resolve().parent / "prompts" / "bank_extract.md"
    context = statement_text.split("Date Description Amount", 1)[0].strip()
    client = OpenAI(
        api_key=portkey_api_key,
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-provider": "openai"},
    )

    rows = []
    for transaction_line in transaction_lines:
        prompt = load_prompt(prompt_path, context, transaction_line)
        rows.append(normalize_row(extract_transaction(client, prompt)))
        print(f"Processed {transaction_line}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.out_dir / "bank_transactions.json"
    output_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
