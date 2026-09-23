"""Extract one structured JSON row from each purchase receipt PDF."""

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
REQUIRED_FIELDS = (
    "vendor",
    "transaction_date",
    "description",
    "amount_usd",
    "category",
)
ALLOWED_CATEGORIES = {"cogs_part", "tools_equipment", "shipping"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def load_prompt(prompt_path: Path, receipt_text: str) -> str:
    return prompt_path.read_text(encoding="utf-8").replace(
        "{{receipt_text}}", receipt_text
    )


def extract_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def parse_json_object(output_text: str) -> dict[str, Any]:
    cleaned = output_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned).strip()
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("LLM response was not a JSON object")
    return value


def normalize_row(value: dict[str, Any], source_file: str) -> dict[str, Any]:
    missing = value.get("fields_not_found", [])
    if not isinstance(missing, list):
        missing = []
    missing = [str(field) for field in missing]

    row: dict[str, Any] = {
        field: value.get(field) for field in REQUIRED_FIELDS
    }
    row["source_file"] = source_file

    if row["category"] not in ALLOWED_CATEGORIES:
        if row["category"] is not None and "category" not in missing:
            missing.append("category")
        row["category"] = None

    for field in REQUIRED_FIELDS:
        if row[field] is None and field not in missing:
            missing.append(field)

    row["fields_not_found"] = missing
    return row


def extract_receipt(client: OpenAI, prompt: str) -> dict[str, Any]:
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

    prompt_path = Path(__file__).resolve().parent / "prompts" / "receipts_extract.md"
    client = OpenAI(
        api_key=portkey_api_key,
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-provider": "openai"},
    )

    # The pack includes five files named receipt_*.pdf plus one purchase
    # confirmation whose filename does not use the receipt prefix.
    receipt_paths = sorted(
        path
        for path in args.docs_dir.rglob("*.pdf")
        if path.name.lower().startswith("receipt_")
        or path.name.lower() == "ebay_repair_stand.pdf"
    )
    if not receipt_paths:
        raise SystemExit(f"No receipt PDFs found in {args.docs_dir}")

    rows = []
    for pdf_path in receipt_paths:
        receipt_text = extract_pdf_text(pdf_path)
        prompt = load_prompt(prompt_path, receipt_text)
        extracted = extract_receipt(client, prompt)
        rows.append(normalize_row(extracted, pdf_path.name))
        print(f"Processed {pdf_path.name}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.out_dir / "receipts.json"
    output_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
