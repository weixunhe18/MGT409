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

*Rewritten Sat ~1:40 pm for the current state: Gmail connector built, Fly.io chosen for hosting, MAILBOX_SEND=on in .env.*

```text
You are my technical cofounder finishing my MGT 409 final project "Supplier Whisperer" (project1/supplier-whisperer) while I'm hiking. I'm back around 6 pm ET and cannot answer questions until then.

First read: START_HERE.md, decisions.md (D1–D6), README.md, criteria.md, proposal.md, demo_plan.md, assumptions.md, questions_for_morning.md (my answers are in the table at the top), docs/user_evidence.md, research/competitors_and_impact.md. Use the project's .venv (source .venv/bin/activate). The Portkey key is found automatically in the repo-root .env.

HARD RULES
- NEVER run `python app.py --mailbox` and never open an IMAP/SMTP connection: MAILBOX_SEND=on is set in .env, so it would send REAL email. Gmail work happens only in unit tests with fake IMAP/SMTP objects.
- Never create accounts, never spend money except tiny gpt-6-luna calls through PORTKEY_API_KEY. Keep total live spend under $0.50 (don't raise the app's $1 daily cap). Report the spend in the summary.
- Never print, log, or commit keys or any .env file. Do NOT git push.
- data/raw_private/ is employer data: never commit it, never copy text from it into tracked files, the report or slides. Aggregate numbers only (e.g. "43 real supplier emails replayed, 0 commitments"), and only from data/raw_private/supplier_01/results_live2.json.
- Orchestration and guardrails stay deterministic code. No LLM agent may get a tool that sends, approves, attaches or picks recipients (D1). Guardrails may get stricter, never looser, unless a test proves a false positive on real-looking text.
- Working code beats ambitious code: `python app.py --test` must stay green after every change, and `python app.py --demo --mock` must keep 9/9 "ok". Commit after each step (git add the project folder only; git commit -m "...").
- If blocked, make a reasonable assumption, log it in assumptions.md, and continue. Decisions for me go in questions_for_morning.md under a new heading "Saturday evening".

STEP 1: TOKENOMICS EVIDENCE (max 45 min)
Write scripts/measure_tokens.py that runs the 9-email sample inbox LIVE 3 times on fresh in-memory stores and writes docs/tokenomics.json and docs/tokenomics.md: mean input / cached / output tokens and cost per agent; cost per email type (auto-sent, needs-approval, escalated, blocked = $0); cost of the full 9-email night; then the scale model from proposal.md section 7 recomputed with the MEASURED numbers (400 supplier emails per user per month; 1, 100 and 10,000 users; AgentMail/hosting as separate lines; Fly.io ≈ $2/month per small machine). IMPORTANT: repeated live runs returned identical token counts, which suggests Portkey response caching. Check the response headers/body for a cache indicator, and if caching is on, disable it for the measurement (e.g. Portkey cache-control header) or add a per-run nonce, and say which you did. Then test ONE cost-cutting change live (REASONING_EFFORT=low vs default, or a shared cached prompt prefix) and report token/cost deltas AND whether any outcome or draft changed.

STEP 2: SCREENSHOTS (max 40 min)
Start `python app.py --reset --replay --no-browser` (NOT --mailbox; live engine, or --mock with "mock" in filenames if live breaks). Poll GET http://127.0.0.1:8000/api/state until stats.total == 9 and the queue is empty. Capture 1440x1000 PNGs into docs/screenshots/ with headless Chrome (--headless=new --hide-scrollbars --window-size=1440,1000 --virtual-time-budget=5000 --screenshot=...): 01_brief "/#tab=inbox", 02_trace_auto_sent_email9 "/#run=9", 03_engineering_change_email1 "/#run=1", 04_escalation_email3 "/#run=3", 05_quarantine_email4 "/#run=4", 06_impersonation_email7 "/#run=7", 07_thread_memory_email8 "/#run=8", 08_security "/#tab=security", 09_sent "/#tab=sent", 10_compose "/#tab=compose". Then POST /api/settings {"risk_tolerance":"low"} and POST /api/replay {"reset":true} (header X-Requested-With: supplier-whisperer), wait, capture 11_risk_low "/#tab=inbox". Check the run ids match the emails (open /api/state) and fix the URLs if not. Save `python app.py --test` and `python app.py --demo --live` outputs to docs/screenshots/test_output.txt and live_demo_output.txt. Open every PNG and retake any that didn't render. Reset risk to medium and stop the server.

STEP 3: REPORT DRAFT (max 75 min)
Create docs/report_src.html: one clean, print-friendly HTML report for a smart manager who has never seen the app, 10–15 printed Letter pages, system fonts, max-width ~820px, page break before each H2. Use EXACTLY the 8 sections, in the order from criteria.md section 2, with proposal.md as the outline, docs/tokenomics.md for numbers, docs/screenshots/*.png as evidence, research/competitors_and_impact.md for sourced claims (keep links). Every number must be sourced (link), measured (tokenomics.json, app output, or the aggregate real-thread replay), or marked "(Wei's estimate)". TODO boxes where evidence is missing (especially the real-user quote and baseline numbers). Must include: an inline-SVG architecture diagram (no mermaid), one LIVE run of email 9 traced step by step, the competitor table, the safety table with test names, the risk-tolerance table, the Gmail mailbox safety design (DKIM/DMARC, Reply-To ignored, caps, dry-run default, old-mail cutoff), the real-thread replay findings in aggregate (what it caught, what was fixed: wire≠payment, factory-attached, status quantities, no holding reply without a question), decisions D5/D6, and limits plus next steps. Build with `python scripts/inline_images.py docs/report_src.html report.html`, print to docs/report_preview.pdf with headless Chrome (--print-to-pdf) and confirm 10–15 pages.

STEP 4: FLY.IO DEPLOYMENT PREP, NO ACCOUNT NEEDED (max 45 min)
I chose Fly.io for an always-on mailbox (decisions.md: add D7 recording why polling on an always-on host beats webhooks: Gmail push needs Pub/Sub + watch renewal; polling needs no public endpoint). Add a Dockerfile (python:3.12-slim, requirements.txt, non-root user), .dockerignore (exclude .venv, data/raw_private, data/runtime, .env, .git), and fly.toml with NO public [[services]]/[http_service] (the dashboard has no login, so it must not be internet-reachable), a volume mounted at /data, WHISPERER_DB=/data/sample-mailbox.db, and the command `python app.py --live --mailbox --no-browser`. Decide how I reach the dashboard privately (e.g. `fly proxy 8000` over Fly's private network, or `fly ssh console`), make the server bind safely for that (keep the existing refusal to bind publicly without auth; if a new flag is needed, make it explicit and test it), and document it. Write docs/deploy_fly.md: exact commands for ME to run later (fly auth signup/login, fly launch --no-deploy, fly volumes create, fly secrets set PORTKEY_API_KEY GMAIL_APP_PASSWORD MAILBOX_SEND MY_PERSONAL_EMAIL, fly deploy, fly logs, how to stop it), expected monthly cost, and how to roll back. If Docker is installed, run `docker build` to verify; do not run anything that talks to Fly.

STEP 5 (STRETCH, only if 1–4 are done): APPROVE BY EMAIL
So I can approve drafts from my phone when the laptop is off: when a run ends NEEDS_APPROVAL or ESCALATED in mailbox mode, email MY_PERSONAL_EMAIL a short digest (supplier, question summary, the draft, run id). If I reply from MY_PERSONAL_EMAIL with DKIM/DMARC pass and the first line "APPROVE <id>" the draft is approved through Pipeline.approve (same compliance checks, needs_force → not sent, tell me why); "EDIT <id>" followed by text approves my edited text through the same checks; anything else is ignored. Never act on approvals from any other address, and never let supplier mail trigger approvals. Unit tests with fake IMAP/SMTP only. Document in README. (Note: MY_PERSONAL_EMAIL in .env is currently the agent's own address; put a question for me about that in questions_for_morning.md.)

FINALLY write docs/hike_summary.md: what you did, what is verified vs not, live spend, TODOs for me, anything that worried you. Commit.
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
