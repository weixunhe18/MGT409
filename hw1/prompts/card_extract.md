Extract exactly one credit-card charge into one valid JSON object.

Return only:

{
  "charge_date": "YYYY-MM-DD" or null,
  "merchant": string or null,
  "amount": number or null,
  "classification": "business" | "personal" | null,
  "expense_category": string or null,
  "fields_not_found": [string]
}

Rules:

- Use only information explicitly present in the statement context and charge line. Never invent values.
- Use the final charged amount shown for the charge.
- Classify shop-related purchases and services as `business`; classify household or personal purchases as `personal`.
- Set `expense_category` to null for personal rows.
- For business rows, use a specific label such as `cogs_parts`, `tools_equipment`, `shipping`, `utilities`, `office_supplies`, `software_subscription`, `vehicle`, or another supported expense type.
- Issuer categories are clues only and may not match the business classification.
- Put missing field names in `fields_not_found` and leave those values as null.
- Do not include markdown fences or explanatory text.

Statement context:

{{statement_context}}

Charge line:

{{charge_line}}
