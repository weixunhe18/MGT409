# Hike session summary (Sat Oct 24, ~2–6 pm ET, unattended)

All five steps are done and committed locally (**not pushed**). `python app.py --test`: **99 tests OK**.
`python app.py --demo --mock`: **9/9 ok**. `python app.py --mailbox` was **never** run, and no IMAP/SMTP connection
was opened (the Gmail work is tested only with fake servers).

| Commit | What |
|---|---|
| `f371149` | Step 1 tokenomics (live) + Step 2 screenshots |
| `d8c4e0f` | Step 4 Fly.io prep + Step 5 approve-by-email |
| `e361599` | Step 3 report draft (`report.html`, 13 Letter pages) |
| (this one) | this summary |

## What I did

**Step 1: Tokenomics** (`scripts/measure_tokens.py` → `docs/tokenomics.md` / `.json`)
- 3 live nights at the default reasoning effort and 3 at `REASONING_EFFORT=low`, each on a fresh in-memory store.
- **$0.0040 per 9-email night; $0.00044 per email** on this mix; threats cost $0. Per agent call: manager $0.00023,
  context $0.00014 (87% of its input cached), email agent $0.00021, compliance $0.00014.
- Scale (400 emails/user/month): model **$0.18/user/month**; 100 users $219.78/month total, 10,000 users
  $15,377.63/month, of which AgentMail list price is $13,400. With Gmail instead of AgentMail: $19.78 and $1,977.63.
- **Cost cut tested live: low reasoning effort = −15% cost, −22% output tokens, same outcome distribution.** Not
  switched on (your call, question 4).
- **The Portkey cache mystery is solved:** repeat runs were Portkey response-cache HITs (same stored answer, same
  token counts). The app now logs `x-portkey-cache-status` per call and shows it in the trace. New setting
  `PORTKEY_CACHE=refresh` forces fresh answers; the measurement used it (header `REFRESH` on all 132 calls). Note:
  a tiny 2-call probe showed `MISS`, so the cache only appears on real repeated prompts.

**Step 2: Screenshots** (`docs/screenshots/`, 11 PNGs, all opened and checked)
- Taken from a fresh (uncached) live replay. Run ids 1–9 match email order, so the planned URLs were right.
- `11_risk_low.png` shows 0 auto-sends at Low. Risk is back at Medium; the server is stopped.
- Also `email9_trace_live.json` (the traced run in the report), `test_output.txt`, `live_demo_output.txt`.

**Step 3: Report** (`docs/report_src.html` → `report.html`, preview `docs/report_preview.pdf`, **13 pages**)
- Rubric's 8 sections in order, inline-SVG diagram, email 9 traced step by step, competitor/safety/risk tables,
  Gmail safety design, real-thread replay in aggregate only, D5/D6, limits and next steps. Every number is linked,
  measured, or marked "(Wei's estimate)". 13 pages leaves room for your evidence (limit 15).

**Step 4: Fly.io prep** (no account, nothing talked to Fly): `Dockerfile` (non-root), `.dockerignore`, `fly.toml`
with **no public service**, volume at `/data`, `docs/deploy_fly.md` (exact commands, ~$2–3/month, rollback),
decisions.md **D7**. New explicit flag `--fly-private`: binds only Fly's private `fdaa::/16` address (refuses
anything else) and only answers `Host: localhost`, so you reach the dashboard with `fly proxy 8000`.

**Step 5: Approve by email** (stretch, done): digest to `MY_PERSONAL_EMAIL` for NEEDS_APPROVAL/ESCALATED mailbox runs;
a DKIM/DMARC-verified reply from that address with first line `APPROVE <id>` or `EDIT <id>` + text goes through
`Pipeline.approve` (same checks, never forced; a blocked edit is emailed back with reasons). Supplier mail can never
approve. 9 new tests with fake IMAP/SMTP. README documents it. **It's off right now** because `MY_PERSONAL_EMAIL` is
the agent's own address (question 1).

## Verified vs not verified

| Verified | Not verified |
|---|---|
| 99 tests, mock 9/9, after every commit (commit 1's snapshot tested on its own) | `docker build` (Docker isn't installed), so the image and `setpriv` in the entrypoint are untested |
| Live measurement, screenshots, report build, PDF page count | Anything on Fly.io (`fly proxy` to a machine with no services) |
| Approve-by-email logic against fake IMAP/SMTP | Approve-by-email against real Gmail (needs `MY_PERSONAL_EMAIL` changed, and you at the keyboard) |
| Secrets scan of tracked files: no key, no `.env`, nothing from `data/raw_private/` | A visual read of every PDF page (no PDF renderer here; I checked per-page text and the diagram) |

## Live spend

About **$0.03–0.05** this session (upper bound $0.05): measurement $0.0222 (exact), three fresh runs ≈ $0.012, plus
four runs that turned out to be Portkey cache hits (≤ $0.016 if Portkey bills those at all). Well under the $0.50
limit; the $1 daily cap was not touched. **Running total ≈ $0.12 of the $40 course budget** (~$0.07 before today),
on day ~1 of 6 weeks: no risk of overspending.

## TODOs for you

1. Answer the new **"Saturday evening"** questions in `questions_for_morning.md` (personal email for approvals,
   Fly/TA access, low reasoning effort, email 2's live variance).
2. Fill `docs/user_evidence.md` (§A baseline, §B real-user session + quote with permission, §C before/after). The
   report has yellow TODO boxes in §2 and §7 for these; the dinner session will fold them in.
3. Read `report.html` end to end: you're responsible for every word and number. Check my wording of your five years
   of experience in §2 and the "Wei's estimate" numbers (3–6 h/week, 400 emails/month, 1 machine per 100 users).
4. When you want an always-on mailbox: follow `docs/deploy_fly.md` (stop the laptop poller first).

## Things that worried me

- **Email 2 (Lily) is unstable live:** escalated in ~2 of 3 runs (the live manager reads a timing question), though the
  demo script expects "needs approval". It errs strict, so I left the guardrails and sample data alone. During the
  video it may show as "Needs your decision"; say so or reword the sample email.
- **Portkey's cache affects demos:** without `PORTKEY_CACHE=refresh`, a re-run of the demo inbox replays stored answers
  in ~1 s. That's fine (and free), but don't present cached timings or token counts as fresh measurements. The trace
  now labels them.
- **The real-thread replay is sobering:** only 1 of 43 real emails was auto-answerable (late-stage thread). The
  report says so plainly and frames the value as triage + drafts + holding replies; the 40–60% hypothesis needs
  early-stage DFM threads.
- **Double replies:** if the laptop mailbox and a future Fly deployment poll at the same time, both answer. Documented
  in `docs/deploy_fly.md`; run only one.
- `START_HERE.md` still says 77 tests and predates the Gmail live test; the dinner session should refresh it.
