Reconcile the financial evidence into a concise income-statement decision log for January 2026.

Return only a valid JSON array. Each array element must be one reconciled item, not one raw transaction line.

Each row must have this shape:

{
  "id": "short-kebab-case-slug",
  "sources": ["document filename"],
  "amounts_seen": [{"source": "document filename", "amount": number}],
  "included_in_income_statement": "yes" | "no",
  "amount_used_in_income_statement": number,
  "resolution": string,
  "plain_english": string
}

Rules:

- Use only the supplied output JSON files and email text. Do not use information that is not in those files.
- The reviewed PDFs are intentionally excluded; do not request or infer their contents.
- Create one row for each amount that needs reconciliation or one clear income-statement inclusion/exclusion decision. Do not reproduce every raw line when it does not need a decision.
- Reconcile duplicates across documents. For example, when a receipt and a card transaction represent the same purchase, list both sources but count the purchase once.
- If a receipt amount is explicitly described as only part of a larger card charge, book the larger charge once and do not add the receipt amount. A separate same-vendor bank debit is a separate amount unless the evidence explicitly links it to that charge.
- In this evidence set, the $88.70 Park Tool receipt is only part of the $127.40 Park Tool card charge: book $127.40 once, do not add $88.70, and separately book the $344.55 Park Tool bank debit.
- `amounts_seen` must list every directly relevant amount and its source filename. Do not list unrelated amounts.
- Include revenue and expenses that belong in the January income statement. Exclude owner draws, transfers, personal spending, liabilities, and non-income-statement items.
- Use 0 for `amount_used_in_income_statement` when `included_in_income_statement` is `no`.
- `amount_used_in_income_statement` must represent the final amount to book after reconciliation, not a raw line amount, subtotal, or duplicated supporting amount.
- For included rows, it must be the final amount chosen in `resolution` and `plain_english`.
- Before returning each row, check that `amount_used_in_income_statement` agrees numerically with the final amount described in its explanation.
- Perform all arithmetic carefully in cents. When a row combines several amounts, add the listed components explicitly and use that exact sum; never estimate or copy a nearby total.
- Do not double-count an amount merely because it appears in multiple documents.
- Do not invent missing dates, vendors, amounts, or accounting conclusions unsupported by the supplied evidence.
- Keep each `plain_english` explanation understandable to a non-accountant and explain how the sources were matched and why the final amount was chosen.
- Do not include markdown fences or explanatory text outside the JSON array.

Evidence files:

{{evidence}}
