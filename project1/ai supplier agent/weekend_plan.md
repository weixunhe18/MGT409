# Weekend plan → submission Mon Oct 26, 6:00 PM ET (Canvas)

| When | Who | Goal |
|---|---|---|
| **Sat morning (before 2 pm)** | You, ~75 min | Python running, live key tested, decisions made, repo created |
| **Sat 2–6 pm (hike)** | Claude Code, unattended | Live hardening → measured tokenomics → screenshots → report draft |
| **Sun afternoon** | You, ~90 min | Real-user session, your baseline numbers, optional demo video |
| **Sun 7–10 pm (dinner)** | Claude Code, unattended | Evidence into report → reveal.js slides → fresh-clone QA |
| **Mon (before 6 pm)** | You, ~30 min | Read-through, push, submit |

---

## Saturday morning checklist (you)

1. **Answer `questions_for_morning.md`.** Write your answers inline. Claude reads them later. `decisions.md` already
   records D1–D4 (PydanticAI, real email, the John persona, webhooks).
2. **Move to the personal machine:** copy the whole folder (e.g. to `~/dev/supplier-whisperer`). There's no local
   database to copy; on the work machine it lives outside the repo. Then, in the new folder:
   ```bash
   python app.py --test
   ```
   You should see **66 tests OK**. Then run `python app.py` and click **▶ Run demo inbox**. Spend 5 minutes clicking
   around.
3. **Create the repo:**
   ```bash
   git init
   ```
   Then `git add -A` and `git commit -m "Supplier Whisperer MVP"`, and create a GitHub repo (public, or private + add
   `zlisto`). `.gitignore` already excludes `.env`, runtime data and `.claude/settings.local.json`.
   Claude's memory from this session stays on the work laptop, so start the new Claude Code session with:
   *"Read START_HERE.md and decisions.md first."*
4. **Course key:** put `PORTKEY_API_KEY=...` in a `.env` **one folder above** the repo (that's how staff will run it),
   then run:
   ```bash
   python app.py --demo --live --show-drafts
   ```
   If it errors, don't fix it yourself; the hike prompt does that.
5. **Fill section A of `docs/user_evidence.md`** (your baseline numbers, 10 min).
6. **Book a tester for Sunday:** text one or two people who deal with suppliers. A 15-minute Zoom is enough.
7. **Claude Code setup for unattended runs:** open the repo in Claude Code and choose a permission mode that won't
   stall on prompts (auto-accept edits), and allow `python`, `pip install -r requirements.txt`,
   `git add/commit/status/diff`, and your headless browser command. **Don't** allow `git push`.
8. **Optional, for the live-email stretch (D2):** create a Gmail app password for the agent mailbox, and add
   `GMAIL_ADDRESS=...`, `GMAIL_APP_PASSWORD=...` and `MY_PERSONAL_EMAIL=...` to the `.env` one folder up. The hike
   session only builds the connector in **dry-run** (it reads and drafts, never sends). You test real sending yourself
   at 6 pm.

---

## 🥾 Hike session (Sat 2–6 pm): paste this one prompt and go

```text
You are my technical cofounder finishing my MGT 409 final project "Supplier Whisperer" while I'm hiking. I'm back around 6 pm ET and cannot answer questions until then.

First read: START_HERE.md, decisions.md, README.md, criteria.md, proposal.md, demo_plan.md, assumptions.md, questions_for_morning.md (my answers are inline), docs/user_evidence.md, research/competitors_and_impact.md.

HARD RULES
- Never SEND real email (the Gmail connector in STEP 5 runs in dry-run only), never create accounts, never spend money except tiny gpt-6-luna calls through PORTKEY_API_KEY; keep total live spend under $0.50 (don't raise the app's $1 daily cap).
- Orchestration and guardrails stay deterministic code. No LLM agent may get a tool that sends, approves, attaches or picks recipients (decisions.md D1).
- Never print, log, or commit the key or any .env file. Do NOT git push.
- If blocked, make a reasonable assumption, log it in assumptions.md, and continue. Anything that needs my decision goes in questions_for_morning.md under a new heading "Saturday evening".
- Working code beats ambitious code: `python app.py --test` must stay green after every change. Commit after each step (git add -A; git commit -m "...").

STEP 1: PYDANTICAI LIVE PATH + LIVE HARDENING (max 75 min)
Per decisions.md D1: add a PydanticAI client for the 4 live model calls using the course pattern (OpenAIResponsesModel + OpenAIProvider(AsyncOpenAI(api_key=PORTKEY_API_KEY, base_url="https://api.portkey.ai/v1", default_headers={"x-portkey-provider": "openai"})), model gpt-6-luna), with Pydantic output models for Triage, Answers, Draft and Review. Import pydantic_ai lazily ONLY in live mode so `--mock`, `--demo --mock` and `--test` still run on bare Python. Map result.usage() (input, cache-read, output tokens) into the existing Meter so budgets and the dashboard keep working. Keep the urllib client selectable with LLM_CLIENT=urllib as a fallback. Pin versions in requirements.txt, update the README run steps (add `pip install -r requirements.txt`), and add tests with PydanticAI's FunctionModel/TestModel. Then run `python app.py --test` and `python app.py --demo --live --show-drafts`. Compare the 8 live outcomes with `_demo.expected` in data/sample/emails.json. If gpt-6-luna's triage differs, decide whether the model or the expectation is right; you may make deterministic guardrails STRICTER, never looser. If the PydanticAI path can't be made to work within the time box, leave LLM_CLIENT=urllib as the default and say why. Log every change in assumptions.md.

STEP 2: TOKENOMICS EVIDENCE (max 40 min)
Write scripts/measure_tokens.py (no dependencies beyond requirements.txt) that runs the sample inbox LIVE 3 times on fresh in-memory stores and writes docs/tokenomics.json and docs/tokenomics.md with: mean input / cached / output tokens and cost per agent; cost per email type (auto-sent, needs-approval, escalated, blocked = $0); cost of the full 8-email night; then the scale model from proposal.md section 7 recomputed with the MEASURED numbers (assume 400 supplier emails per user per month; show 1, 100 and 10,000 users; show AgentMail infrastructure cost as a separate line using research/competitors_and_impact.md). Then test ONE cost-cutting change live (e.g. REASONING_EFFORT=low vs default, or restructuring prompts so the shared prefix is cached) and report the token and cost deltas AND whether any outcome or draft quality changed. That's the rubric's "cost-cutting and whether it hurt performance".

STEP 3: SCREENSHOTS (max 40 min)
Start `python app.py --reset --replay --no-browser` (live engine; if live is broken use --mock and put "mock" in filenames). Poll GET http://127.0.0.1:8000/api/state until stats.total == 8 and app.queue == 0. Capture 1440x1000 PNGs into docs/screenshots/ with headless Chrome or Edge (--headless=new --hide-scrollbars --window-size=1440,1000 --virtual-time-budget=5000 --screenshot=...) for these URLs: 01_brief "/#tab=inbox", 02_trace_email1 "/#run=1", 03_escalation_email3 "/#run=3", 04_quarantine_email4 "/#run=4", 05_impersonation_email7 "/#run=7", 06_thread_memory_email8 "/#run=8", 07_security "/#tab=security", 08_sent "/#tab=sent", 09_compose "/#tab=compose". Then POST /api/settings {"risk_tolerance":"low"} and POST /api/replay {"reset":true} (both with header X-Requested-With: supplier-whisperer), wait, and capture 10_risk_low "/#tab=inbox". Save `python app.py --test` and `python app.py --demo --live` outputs as docs/screenshots/test_output.txt and live_demo_output.txt. Open every PNG and retake any where the drawer or data didn't render. Reset risk to medium afterwards.

STEP 4: REPORT DRAFT (remaining time)
Create docs/report_src.html: one clean, print-friendly HTML report for a smart manager who has never seen the app. It must be 10–15 printed Letter pages, use system fonts, max-width ~820px, and put a page break before each H2. Use EXACTLY the 8 sections, in the order from criteria.md section 2. Use proposal.md as the outline, docs/tokenomics.md for numbers, docs/screenshots/*.png as evidence (relative img src), and research/competitors_and_impact.md for sourced claims (keep the links). Every number must be sourced (link), measured (tokenomics.json or app output), or explicitly marked "(Wei's estimate)" from docs/user_evidence.md. Put clearly marked TODO boxes where evidence is missing (especially the real-user quote). Must include: an architecture diagram as inline SVG (no mermaid, it must render offline), one LIVE run of email 1 traced step by step with screenshots, the named-competitor table, the safety table with test names, the risk-tolerance table, and limits plus next steps. Build with `python scripts/inline_images.py docs/report_src.html report.html`, then print to docs/report_preview.pdf with the headless browser (--print-to-pdf) and confirm 10–15 pages; adjust if not.

STEP 5 (STRETCH: only if steps 1–4 are done AND GMAIL_ADDRESS / GMAIL_APP_PASSWORD exist in .env): LIVE MAILBOX CONNECTOR IN DRY-RUN
Per decisions.md D2: add supplier_agent/mailbox.py (stdlib imaplib/smtplib/email) and `python app.py --mailbox` that polls the Gmail inbox over IMAP every 60 s for unseen mail, converts each message into the same normalized email dict the webhook path produces, and runs it through the SAME pipeline. Required safety: allowlisted senders must have dkim=pass or dmarc=pass in Authentication-Results, otherwise treat them as unknown; reply only to the authenticated From, never Reply-To; per-sender and global daily send caps; In-Reply-To/References headers on replies; display name from policy.json persona ("John, Northfield Outdoor Labs"); add "@yale.edu" as a demo-only allowlist entry and MY_PERSONAL_EMAIL from .env. MAILBOX_SEND defaults to "dry-run": approved or auto-sent replies are only shown in the dashboard and outbox, never transmitted. Do NOT flip it on. Add unit tests with fake IMAP/SMTP objects. Document setup in README under "Optional: live mailbox".

FINALLY write docs/hike_summary.md: what you did, what is verified vs not, TODOs for me, anything that worried you.
```

**Individual fallback prompts** (if the mega-prompt stalls, paste just the step you need):

```text
Live mode is failing. Run `python app.py --demo --live` and read the error in the agent trace or terminal. Fix supplier_agent/llm.py (Portkey Responses API via urllib; headers Authorization: Bearer PORTKEY_API_KEY and x-portkey-provider: openai; model gpt-6-luna) with the smallest change that works. Add a unit test with a scripted fake model reproducing the failure. Keep `python app.py --test` green. Never print the key. Log the fix in assumptions.md.
```

```text
Regenerate the report: rebuild docs/report_src.html → report.html with scripts/inline_images.py, print to PDF with a headless browser, and make the page count 10–15 Letter pages without dropping any rubric evidence (criteria.md section 6). List what you cut or expanded in docs/hike_summary.md.
```

---

## Sunday afternoon checklist (you)

1. **Read `docs/hike_summary.md`** and fix anything it flags that needs you.
2. **Real-user session (15 min)**, using `docs/user_evidence.md` section B. Get one verbatim quote, with permission.
3. **Before/after measurement:** fill section C (live arrival-to-reply time for email 9 from the trace).
4. **Optional demo video (2–3 min):** follow `demo_plan.md`, record with Win+Alt+R (Xbox Game Bar) or OBS, and save as
   `docs/demo.mp4` (don't commit if it's over 50 MB; upload to Canvas instead).

---

## 🍽️ Dinner session (Sun 7–10 pm): paste this one prompt and go

```text
You are my technical cofounder finishing my MGT 409 final project "Supplier Whisperer" while I'm at dinner (back ~10 pm ET, no questions until then). Read docs/hike_summary.md, docs/user_evidence.md (filled in this afternoon), questions_for_morning.md, criteria.md, demo_plan.md.

HARD RULES: same as yesterday. No real email, no accounts, no spend beyond tiny gpt-6-luna calls, never print or commit .env or keys, do NOT git push, `python app.py --test` stays green, commit after each step, log assumptions in assumptions.md.

STEP 1: EVIDENCE INTO THE REPORT (max 45 min)
Update docs/report_src.html: the Impact section gets my baseline numbers, the real-user session, the verbatim quote (only if marked "with permission"), and the before/after turnaround from docs/user_evidence.md. Recompute every derived number (hours saved, $ per engineer per year using BLS $50/h, cost at 100 and 10,000 users). Remove every TODO you can; list the ones you can't. Rebuild report.html with scripts/inline_images.py and re-check 10–15 pages.

STEP 2: SLIDES (max 60 min)
Create docs/slides_src.html → slides.html: a reveal.js deck loaded from a CDN (https://cdn.jsdelivr.net/npm/reveal.js@5), 10 slides max, following the suggested order in criteria.md section 3 and the story in demo_plan.md. Big text, one idea per slide, consistent dark-navy style matching the app. Include the inline-SVG architecture diagram, 3–4 screenshots (brief, trace, quarantine, escalation), and the key numbers: cost per email, cost at 100/10k users, 3 threats stopped at $0, turnaround before vs after, the real-user quote. Arrow keys navigate, F goes fullscreen. Inline images with scripts/inline_images.py, then open slides.html from a DIFFERENT folder to prove all images are embedded.

STEP 3: FINAL QA (max 45 min)
- `python app.py --test` green; `python app.py --demo --mock` shows 9/9 "ok".
- Fresh-clone test: git clone this repo into a new temp folder, put a .env ONE LEVEL ABOVE the clone, follow README.md literally, and time it (must be well under 10 minutes). Start the app, run the demo inbox, confirm the live engine. Fix the README if any step was unclear.
- Secrets scan of the working tree AND git history: no PORTKEY keys, no "sk-" strings, no real whsec_ secrets, no .env files tracked.
- Copy report.html and slides.html to another folder and open them there: every image must show.
- Check every rubric line in criteria.md section 6 against the report and slides; write docs/submission_checklist.md (✓/✗ + where) and fix the ✗ items you can.

FINALLY commit (no push) and write docs/dinner_summary.md with the exact Monday steps: push command, repo visibility/zlisto collaborator, the files to upload to Canvas (repo URL, report.html, slides.html, optional video), and remaining risks.
```

---

## Monday (you, ~30 min, before 6 pm ET)

1. Skim report.html and slides.html end to end. **You're responsible for every word and number.**
2. `git push`, check the repo page (README renders, no `.env`), add `zlisto` if it's private.
3. On a second folder or machine: clone → `.env` one level up → `python app.py` → it runs. This is the 10-minute rule.
4. Submit on Canvas: **repo URL, report.html, slides.html** (+ optional video).
