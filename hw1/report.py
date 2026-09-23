"""Build a one-page HTML summary from the exported JSON files."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


INCOME_STATEMENT_NAME = "income_statement_jan2026.json"
RECONCILIATION_NAME = "reconciliation_log.json"
JUDGMENT_CALLS_NAME = "judgment_calls.json"
REPORT_NAME = "income_statement.html"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def load_json(out_dir: Path, filename: str) -> Any:
    path = out_dir / filename
    if not path.is_file():
        raise SystemExit(f"Required JSON file does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def money(value: Any) -> str:
    return f"${float(value):,.2f}"


def text(value: Any) -> str:
    return html.escape(str(value))


def sources(values: list[str]) -> str:
    return ", ".join(text(value) for value in values)


def expense_rows(statement: dict[str, Any]) -> str:
    return "\n".join(
        "<tr>"
        f"<td>{text(line['label'])}</td>"
        f"<td>{text(line['category'])}</td>"
        f"<td class=\"amount\">{money(line['amount_usd'])}</td>"
        f"<td>{sources(line['sources'])}</td>"
        "</tr>"
        for line in statement["expense_lines"]
    )


def revenue_rows(statement: dict[str, Any]) -> str:
    return "\n".join(
        "<tr>"
        f"<td>{text(line['label'])}</td>"
        f"<td class=\"amount\">{money(line['amount_usd'])}</td>"
        f"<td>{sources(line['sources'])}</td>"
        "</tr>"
        for line in statement.get("revenue_lines", [])
    )


def excluded_rows(reconciliation: list[dict[str, Any]]) -> str:
    excluded = [
        row
        for row in reconciliation
        if row.get("included_in_income_statement") == "no"
    ]
    if not excluded:
        return '<p class="muted">No excluded rows.</p>'
    return "\n".join(
        "<article class=\"decision\">"
        f"<h3>{text(row['id'])}</h3>"
        f"<p><strong>Amount excluded:</strong> {money(row['amount_used_in_income_statement'])}</p>"
        f"<p>{text(row['plain_english'])}</p>"
        f"<p class=\"sources\"><strong>Sources:</strong> {sources(row['sources'])}</p>"
        "</article>"
        for row in excluded
    )


def judgment_rows(
    judgment_calls: list[dict[str, Any]], reconciliation: list[dict[str, Any]]
) -> str:
    rows = judgment_calls or [
        row
        for row in reconciliation
        if "email_owner_voice_memo.txt" in row.get("sources", [])
    ]
    if not rows:
        return '<p class="muted">No judgment calls recorded.</p>'
    return "\n".join(
        "<article class=\"decision\">"
        f"<h3>{text(row['id'])}</h3>"
        f"<p><strong>Decision:</strong> {text(row.get('resolution', ''))}</p>"
        f"<p>{text(row.get('plain_english', ''))}</p>"
        "</article>"
        for row in rows
    )


def build_html(
    statement: dict[str, Any],
    reconciliation: list[dict[str, Any]],
    judgment_calls: list[dict[str, Any]],
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>January 2026 Income Statement</title>
  <style>
    :root {{ color-scheme: dark; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #10182d; color: #f8f2df; overflow-x: hidden; }}
    body::before {{ content: ""; position: fixed; inset: 0; pointer-events: none; opacity: .12; background-image: repeating-linear-gradient(135deg, #f2a900 0 2px, transparent 2px 22px); }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 2rem 1rem 11rem; position: relative; z-index: 1; }}
    h1, h2 {{ margin-top: 0; color: #ffb703; text-shadow: 2px 2px #8d1b1b; }}
    h1 {{ font-size: clamp(2rem, 5vw, 4rem); letter-spacing: .04em; }}
    section {{ background: #18233d; border: 2px solid #34466d; border-radius: 14px; padding: 1.25rem; margin: 1rem 0; box-shadow: 8px 8px 0 #090f20; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: .65rem .5rem; border-bottom: 1px solid #e3e8ed; text-align: left; vertical-align: top; }}
    th {{ color: #ffcf56; font-size: .85rem; }}
    td {{ color: #f8f2df; }}
    tr:hover td {{ background: #213052; }}
    .amount {{ text-align: right; white-space: nowrap; }}
    .totals {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: .75rem; margin: 1rem 0; }}
    .total {{ background: linear-gradient(135deg, #243b68, #4b1d35); border-radius: 8px; padding: .9rem; border: 1px solid #e09f24; }}
    .total strong {{ display: block; font-size: 1.35rem; margin-top: .25rem; color: #ffe08a; }}
    .decision {{ border-left: 4px solid #ffb703; padding: .25rem 1rem; margin: 1rem 0; background: #221d38; }}
    .decision h3 {{ margin-bottom: .35rem; }}
    .sources, .muted {{ color: #b7c2df; font-size: .9rem; }}
    .ninja-runner {{ position: fixed; z-index: 5; right: clamp(.4rem, 3vw, 2rem); top: 18vh; font-size: 3.5rem; line-height: 1; filter: drop-shadow(4px 5px 0 #080c18); animation: ninja-run 1.1s steps(2, end) infinite, ninja-bob 1.1s ease-in-out infinite; user-select: none; }}
    .ninja-runner::after {{ content: ""; display: block; width: 3.8rem; height: .3rem; margin-top: .25rem; background: #e85d04; border-radius: 50%; opacity: .8; animation: dust 1.1s ease-out infinite; }}
    .cash-altar {{ margin: 3rem auto 0; text-align: center; padding: 2rem 1rem; border: 3px solid #e09f24; border-radius: 20px; background: radial-gradient(circle, #523b17 0 20%, #211a2d 65%); box-shadow: 0 0 30px #e09f2455; }}
    .cash-pile {{ font-size: clamp(3rem, 10vw, 7rem); letter-spacing: -.35em; filter: drop-shadow(0 7px 0 #07101c); animation: cash-pulse 2s ease-in-out infinite; }}
    .cash-altar p {{ color: #ffcf56; font-weight: 700; letter-spacing: .08em; }}
    @keyframes ninja-run {{ 0% {{ transform: translateX(0) rotate(-5deg); }} 50% {{ transform: translateX(-12px) rotate(5deg); }} 100% {{ transform: translateX(0) rotate(-5deg); }} }}
    @keyframes ninja-bob {{ 0%, 100% {{ margin-top: 0; }} 50% {{ margin-top: 14px; }} }}
    @keyframes dust {{ 0% {{ transform: scaleX(.4); opacity: .2; }} 50% {{ transform: scaleX(1); opacity: .9; }} 100% {{ transform: scaleX(.4); opacity: .2; }} }}
    @keyframes cash-pulse {{ 0%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-8px); }} }}
    @media (max-width: 700px) {{ .totals {{ grid-template-columns: 1fr; }} table {{ font-size: .9rem; }} .ninja-runner {{ font-size: 2.5rem; right: .2rem; }} }}
  </style>
</head>
<body>
<div class="ninja-runner" aria-label="Animated ninja runner" title="Keep running toward the net income">🥷</div>
<main>
  <h1>January Income Statement</h1>
  <p>Period: <strong>{text(statement['period'])}</strong></p>
  <div class="totals">
    <div class="total">Revenue<strong>{money(statement['revenue_usd'])}</strong></div>
    <div class="total">Total expenses<strong>{money(statement['total_expenses_usd'])}</strong></div>
    <div class="total">Net income<strong>{money(statement['netincome_usd'])}</strong></div>
  </div>
  <section>
    <h2>Revenue lines</h2>
    <table><thead><tr><th>Label</th><th class="amount">Amount</th><th>Sources</th></tr></thead>
    <tbody>{revenue_rows(statement)}</tbody></table>
  </section>
  <section>
    <h2>Expense lines</h2>
    <table><thead><tr><th>Label</th><th>Category</th><th class="amount">Amount</th><th>Sources</th></tr></thead>
    <tbody>{expense_rows(statement)}</tbody></table>
  </section>
  <section>
    <h2>Excluded personal and business rows</h2>
    {excluded_rows(reconciliation)}
  </section>
  <section>
    <h2>Judgment calls</h2>
    {judgment_rows(judgment_calls, reconciliation)}
  </section>
  <div class="cash-altar" aria-label="Cash pile at the bottom of the page">
    <div class="cash-pile">💵💵💰💵💰</div>
    <p>THE CASH PILE AWAITS</p>
  </div>
</main>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    if not args.docs_dir.is_dir():
        raise SystemExit(f"Documents directory does not exist: {args.docs_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    statement = load_json(args.out_dir, INCOME_STATEMENT_NAME)
    reconciliation = load_json(args.out_dir, RECONCILIATION_NAME)
    judgment_calls = load_json(args.out_dir, JUDGMENT_CALLS_NAME)
    if not isinstance(reconciliation, list) or not isinstance(judgment_calls, list):
        raise SystemExit("Reconciliation and judgment-call JSON files must contain arrays")
    output_path = args.out_dir / REPORT_NAME
    output_path.write_text(
        build_html(statement, reconciliation, judgment_calls), encoding="utf-8"
    )
    print(f"Wrote report to {output_path}")


if __name__ == "__main__":
    main()
