Extract exactly one purchase-receipt record from the receipt text below.

Return only a single valid JSON object with these keys:

{
  "vendor": string or null,
  "transaction_date": string in YYYY-MM-DD format or null,
  "description": string or null,
  "amount_usd": number or null,
  "category": "cogs_part" | "tools_equipment" | "shipping" | null,
  "fields_not_found": [string]
}

Rules:

- Use only information explicitly present in the receipt text.
- Never guess, infer, or invent a value.
- For `amount_usd`, use the final all-in total charged on the receipt or order confirmation, including item costs, shipping, delivery charges, taxes, service fees, and other fees. Do not use an item subtotal or pre-tax amount when a final total is shown.
- Put the names of any missing fields in `fields_not_found`.
- Leave missing values as null.
- Use `cogs_part` for bicycle repair parts/components, `tools_equipment` for tools or equipment, and `shipping` for delivery or postage charges.
- If the receipt contains multiple purchased items, summarize them in `description` while keeping this as one record.
- Do not include markdown fences or explanatory text.

Receipt text:

{{receipt_text}}
