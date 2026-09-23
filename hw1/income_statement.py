"""Roll the reconciliation log into a January 2026 income statement."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


RECONCILIATION_NAME = "reconciliation_log.json"
STATEMENT_NAME = "income_statement_jan2026.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def load_reconciliation(out_dir: Path) -> list[dict[str, Any]]:
    path = out_dir / RECONCILIATION_NAME
    if not path.is_file():
        raise SystemExit(f"Reconciliation file does not exist: {path}")
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise SystemExit(f"Expected a JSON array in {path}")
    return rows


def is_revenue(row: dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(field, "")).lower()
        for field in ("id", "resolution", "plain_english")
    )
    return "revenue" in text


def expense_category(label: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return normalized or "expense"


def build_statement(rows: list[dict[str, Any]]) -> dict[str, Any]:
    included = [
        row
        for row in rows
        if row.get("included_in_income_statement") == "yes"
    ]
    revenue_lines = [
        {
            "label": row["id"],
            "amount_usd": float(row["amount_used_in_income_statement"]),
            "category": "revenue",
            "sources": row["sources"],
        }
        for row in included
        if is_revenue(row)
    ]
    revenue_usd = sum(line["amount_usd"] for line in revenue_lines)

    expense_lines = [
        {
            "label": row["id"],
            "amount_usd": float(row["amount_used_in_income_statement"]),
            "category": expense_category(str(row["id"])),
            "sources": row["sources"],
        }
        for row in included
        if not is_revenue(row)
    ]
    revenue_usd = round(revenue_usd, 2)
    for line in revenue_lines:
        line["amount_usd"] = round(line["amount_usd"], 2)
    revenue_usd = round(sum(line["amount_usd"] for line in revenue_lines), 2)
    for line in expense_lines:
        line["amount_usd"] = round(line["amount_usd"], 2)
    total_expenses_usd = round(sum(line["amount_usd"] for line in expense_lines), 2)
    return {
        "period": "2026-01",
        "revenue_lines": revenue_lines,
        "revenue_usd": revenue_usd,
        "expense_lines": expense_lines,
        "total_expenses_usd": total_expenses_usd,
        "netincome_usd": round(revenue_usd - total_expenses_usd, 2),
    }


def main() -> None:
    args = parse_args()
    if not args.docs_dir.is_dir():
        raise SystemExit(f"Documents directory does not exist: {args.docs_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    statement = build_statement(load_reconciliation(args.out_dir))
    output_path = args.out_dir / STATEMENT_NAME
    output_path.write_text(json.dumps(statement, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote income statement to {output_path}")


if __name__ == "__main__":
    main()
