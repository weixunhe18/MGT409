# Sales Agent Harness

This harness keeps the Nexa sales agent focused on evidence-backed research and bounded outreach drafting. The model may research and write drafts, but it may not take external actions.

## Tools

| Tool | What it does | Inputs | Outputs |
|---|---|---|---|
| `website_research` | Returns Playwright research for the single company in profile mode. | Company website URL is supplied in the run context. | Visible first-party page text, page URLs, status codes, extracted PDF text when available, and crawl-quality counts. |
| `search_public_web_tool` | Searches public web results for possible customer companies in customer-finding mode. | Search query and result limit. | Candidate result titles and URLs. Search results are leads only, not verified evidence. |
| `research_company_website` | Crawls a candidate’s official website with Playwright and prioritizes company, property, facilities, location, operations, sustainability, and report pages. | Candidate website URL. | Page text, source URLs, status codes, first-party PDF text when accessible, and crawl-quality counts. |

The agent has no email-sending tool, form-submission tool, login tool, purchasing tool, shell tool, or arbitrary network-action tool.

## Stopping rules

The agent must stop when:

- It has produced the requested number of qualified targets, or has exhausted the reasonable candidate set.
- Each retained target has a seller-fit explanation, source URLs, and either a public contact email or an explicit missing-contact note.
- Each retained target has one draft email with `status: "draft_only"`.
- A website returns access denied, repeated HTTP errors, or unusable content; record the failure and move on rather than repeatedly retrying.
- A candidate cannot be shown to fit the seller after reviewing its official website; reject it with a reason.
- A required input file is missing or malformed.
- A tool repeatedly fails, the evidence becomes contradictory, or the model cannot maintain source attribution.

Operational bounds:

- A normal profile crawl is limited to 20 pages and 8 PDFs per website.
- Candidate website research is limited to 8 pages per candidate.
- The agent model is configured for at most two output retries.
- The requested target count is a ceiling, not a requirement to pad the list with weak leads.
- A later revision should add an explicit maximum number of model/tool steps per run; until then, the operator should stop a run that loops or keeps issuing redundant searches.

## Guardrails

The agent must not:

- Invent company facts, locations, room counts, building sizes, water assets, contact names, email addresses, customer pain, budgets, or trigger events.
- Treat search-result snippets as verified evidence; verify claims on the candidate’s official website.
- Present common-sense facility hypotheses as facts. Label them as hypotheses and state what discovery must confirm.
- Claim that Nexa can perform an unsupported function, guarantee savings, prevent every leak, or replace another system.
- Guess an email format or use a private/personal address when no public business email is available.
- Send email, submit a form, contact a prospect, log in, create an account, or make any other external side effect.
- Bypass Cloudflare, Akamai, robots restrictions, authentication, paywalls, or other access controls.
- Continue crawling a blocked or failing site indefinitely.
- Store API keys, hidden chain-of-thought, passwords, or other secrets in outputs or audit logs.
- Run unbounded searches or spend beyond the project budget. If usage or cost becomes available, record it and stop before exceeding the approved budget.

## Required outputs and audit trail

Customer-finding runs write:

- `output/targets.json`: only qualified target companies, with evidence, sources, fit rationale, contact status, and unknowns.
- `output/emails.json`: targeted drafts only; every draft is marked `draft_only`.
- `output/audit_log.json`: start/stop times, operational notes, tool names, arguments, result summaries, failures, rejected candidates, and output files.

The audit log records concise operational reasoning such as “candidate rejected because no seller-fit evidence was found.” It does not record private model chain-of-thought.
