Extract exactly one structured transaction row from the bank-statement line below.

Return only one valid JSON object with these keys:

{
  "date": "YYYY-MM-DD" or null,
  "description": string or null,
  "amount": number or null,
  "classification": "business" | "personal" | null,
  "credit_or_debit": "credit" | "debit" | null,
  "accounting_label": string or null,
  "fields_not_found": [string]
}

Rules:

- Use only the information in the statement context and transaction line. Never invent values.
- `amount` must be a positive numeric dollar amount. Use `credit_or_debit` to indicate money in or money out.
- Use `credit` for money entering the account and `debit` for money leaving it. “Debit” is the conventional spelling for money out.
- Use `classification` = `business` for business activity and `personal` for personal activity. For revenue, use `business` unless the statement explicitly says otherwise.
- Use `accounting_label` = `revenue`, `expense_rent`, `expense_utilities`, `expense_cogs_parts`, `expense_insurance`, `expense_tools_equipment`, `expense_bank_fee`, `owner_draw`, `transfer`, or another specific `expense_<type>` label supported by the text.
- Treat transfers explicitly marked as personal or owner draw, and personal ATM withdrawals, as `owner_draw`, not business expenses.
- Treat incoming deposits as `revenue` when they are business sales or services. Use `transfer` for transfers that are not revenue.
- Put missing field names in `fields_not_found` and leave those values as null.
- Do not include markdown fences or explanatory text.

Statement context:

{{statement_context}}

Transaction line:

{{transaction_line}}
