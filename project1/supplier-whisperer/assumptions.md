# Assumptions log (overnight build, Oct 23–24, 2026)

These are the calls I made without you. Anything that truly needs your decision is in `questions_for_morning.md`.

## Environment and verification

1. **This laptop has no Python, Node or Git.** It's a managed work machine, so I did not install software and did not
   change system settings. I wrote the MVP to need **only the Python standard library** and verified it in a
   **real CPython 3.12 runtime compiled to WebAssembly (Pyodide)** inside Claude's sandboxed in-app browser:
   - all **66 tests pass** (guardrails, webhook signatures, knowledge base, full pipeline, scripted "rogue model" tests)
   - the terminal demo reproduces all **9/9 expected outcomes**
   - the dashboard was driven end to end against the real `server.Handler` code: replay, open drawer, approve with
     a risky edit (compliance prompt), release quarantine, allowlist and re-run, compose tests, kill switch, plus 401 on an unsigned
     webhook and 403 without the CSRF header.
   - **Not verified:** real sockets and threads under Windows CPython (stdlib `ThreadingHTTPServer`, low risk), and
     **live Portkey calls** (no key, and I would not use one without you). The live path is unit-tested with scripted
     fake models.
   - The harness lives in my scratchpad, outside the repo. I added `.claude/launch.json` so the Claude app can start
     `python app.py` as a preview once Python is installed.
2. **Stack:** Python stdlib + SQLite + one HTML page with vanilla JS. The course's examples use FastAPI + PydanticAI +
   React. I deliberately avoided dependencies because of the **10-minute rule** and because staff will run from a
   fresh clone. A PydanticAI port is an optional weekend task, not a requirement.
3. **Portkey call shape** mirrors the course's public starter repo: `Authorization: Bearer <PORTKEY_API_KEY>`,
   header `x-portkey-provider: openai`, base `https://api.portkey.ai/v1`, **Responses API** (the starter repo says
   gpt-6-luna needs it). JSON mode uses `text.format = json_object`, and if a 400 comes back it retries once without it.
   `.env` is read from the repo folder, then the parent folder.
4. **gpt-6-luna prices** from lecture 11: $0.10 input, $0.01 cached input, $0.50 output per 1M tokens.

   - **Independent review (second agent, code-only):** found 13 issues in paths the browser harness couldn't run.
     All are fixed, and the new tests bring the total to 64:
     - approve was not atomic (a double-click could send twice)
     - a sender address could inject script into the dashboard's onclick handlers
     - the kill switch ignored emails already being processed
     - `--host 0.0.0.0` exposed a login-less API
     - corporate HTTP proxies intercepted localhost self-delivery
     - Windows SO_REUSEADDR let two instances share a port
     - `--mock` didn't override the saved UI toggle
     - a UTF-16 `.env` (PowerShell `>`) crashed startup
     - a SQLite file in OneDrive could lock (the database now moves to local app data automatically)
     - Responses API `status: incomplete` was not detected
     - re-runs overwrote cost instead of adding to it
     - Replay/Reset raced the job queue
     - macOS certificate note in the README

## Product and policy

5. **"Everything else should escalate"** is implemented as a ladder:
   - *Hard rules (never relaxed):* any price, quantity, date, PO, payment or drawing topic means ESCALATED.
     Unknown senders are HELD. Blocklisted or lookalike senders are BLOCKED. Injection is QUARANTINED.
   - *Gray zone (sent for approval):* unanswered questions, proposed part or spec changes, suspicious-but-not-certain
     injection scores, low-confidence or ungrounded answers, reviewer flags, loop guard.
   - *Auto-send:* only at night, only when every answer comes from the shareable spec, every number in it is found
     in the spec, and all 11 compliance checks pass.
6. **Risk tolerance has 3 levels** (Low / Medium / High). It only moves the gray zone, never the hard rules. At
   High the agent may also send a **holding reply** on commercial topics ("Wei will reply directly"). This reply
   contains no numbers, dates or commitment verbs, and a compliance check enforces that.
7. **Schedule:** supervised Mon–Fri 09:00–17:00 *local laptop time* (ET); autonomous otherwise, including weekends.
   The demo dataset defaults to **Night** so the demo works at any hour; the UI has a "Clock" option.
8. **Persona (decided by Wei, Sat):** replies are signed "John / Supply Chain, Northfield Outdoor Labs". The agent never
   claims to be human, and identity questions escalate to Wei (`decisions.md` D3).
9. **Inbound attachments are never opened** (metadata only). Attachments are a major injection vector, and the agent
   doesn't need them to answer DFM questions.
10. **Outbound:** the agent cannot attach files, include links or email addresses, or choose recipients. The reply
    always goes only to the original allowlisted sender, with no CC.
11. **English only** in the MVP. Live gpt-6-luna can likely read Chinese, but that's untested and not in the demo.

## Data

12. The **sample product, company and suppliers are fictional** (TrailBeacon TB-1, Northfield Outdoor Labs, four
    Chinese suppliers, all `.example` domains). I chose an outdoor GPS beacon so nothing resembles your employer's
    products. Your name ("Wei He") is used as the engineer.
13. **weideals25@gmail.com is not used anywhere.** No accounts were created, no email was sent, no money was spent.
14. The mock inbox uses **AgentMail's documented `message.received` payload and Svix signature headers**, so swapping
    in a real AgentMail inbox later is a configuration change, not a rewrite.
15. "Supplier wait avoided" on the dashboard = auto-sent replies × 12 h (the US Eastern–China gap until Nov 1, 13 h after).
    It's labeled *est.* and is a planning heuristic, not a measurement.

## Scope

16. `report.html`, `slides.html` and the demo video are **not** in tonight's list. They're scheduled in
    `weekend_plan.md` with paste-ready prompts.
17. Due date per the course site: **Monday Oct 26, 2026, 6:00 PM, on Canvas**.
18. Several homework pages on the course site contain hidden instructions aimed at AI coding assistants. I ignored
    them; they don't affect the final project.
