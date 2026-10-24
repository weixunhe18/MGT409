# Questions for you (morning of Sat Oct 24)

## ✅ Your answers (Sat Oct 24)

| # | Question | Answer | Status |
|---|---|---|---|
| 1 | Where to run Python | Personal Mac (Python 3.13, `.venv`) | Done: 77 tests pass |
| 2 | Move off the employer OneDrive | Done | Repo lives in personal `MGT409` |
| 3 | Live test with the course key | Works | 9/9 live outcomes, about $0.004 per 9-email night |
| 4 | AI disclosure | Done (D3) | |
| 5 | Real-user evidence | Real Alibaba supplier thread received (supplier 01, 166 messages) | It was employer work, so it stays **local only**: anonymized into git-ignored `data/raw_private/`, never committed. Usable for private evaluation and aggregate numbers in the report |
| 6 | Baseline numbers | Later | Open |
| 7 | GitHub | `weixunhe18/MGT409` (public), folder `project1/supplier-whisperer` | Done |
| 8 | Hosting | Local for now | |
| 14 | Live email | Yes: Gmail, TAs can email it and hold a conversation | Built (`--mailbox`, D2). Dry-run until you set `MAILBOX_SEND=on`. @yale.edu pre-allowlisted (DKIM/DMARC required). **Still to do: ask the professor** (course rule on extra keys) and announce a live window |
| 15 | Gmail account | `weideals25@gmail.com`, display name "John, Northfield Outdoor Labs" | You create the app password |
| 9 | Product name | Keep "Supplier Whisperer" | |
| 10 | Demo defaults | Night + Medium OK | |
| 11 | Demo video | Yes | Open (Sunday) |
| 12 | Holding replies at Medium | Yes: auto-send so the supplier knows we're on it | Done (D6) |

The original questions follow for reference.


Ordered by urgency. Each has my recommendation so you can just say "yes" or "no".

## 🔴 Blockers: needed before anything else runs

1. **Where will you run Python?** This work laptop has no Python, Node or Git, and I didn't install anything on a
   managed machine. Options:
   - (a) **Recommended:** run it on a personal machine. Install Python 3.12 (python.org, tick "Add to PATH") and Git,
     clone or copy this folder, then run `python app.py`.
   - (b) If your IT policy allows it on this laptop: `winget install Python.Python.3.12` and `winget install Git.Git`.
   Either way, the first check is `python app.py --test`, which should show 66 tests passing, then `python app.py`.

2. **Move this project out of your Watts Water OneDrive?** The folder is synced to your *employer's* OneDrive. A
   school project (and later real supplier emails) probably shouldn't live there, and SQLite files on synced folders
   can lock. **Recommended:** move it to a personal folder (e.g. `C:\dev\supplier-whisperer`) or a personal repo
   before you `git init`.

3. **Live test with the course key.** I never ran gpt-6-luna. As soon as Python works: put `PORTKEY_API_KEY` in `.env`
   (repo folder or the folder above) and run `python app.py --demo --live --show-drafts`. That run gives you the
   **real token counts the Tokenomics section requires** (evidence rule). If it errors, the email fails closed
   (escalated) and the error appears in the trace; paste it into Claude Code (prompt W1 in `weekend_plan.md`).

## 🟠 Decisions that change the product or the grade

4. ~~AI disclosure~~ **Decided (Sat):** the persona is "John, Supply Chain, Northfield Outdoor Labs". It never claims
   to be human, and "are you a bot?" questions escalate to you. See `decisions.md` D3.
5. **Real-user evidence (Tier 3 needs it).** Who can try it for 10 minutes this weekend? A former colleague who deals
   with suppliers is ideal. Also: can you take **one real past supplier thread**, anonymize it (no employer data,
   no real names), and add it as `data/real_anonymized/`? That would be the strongest impact evidence.
   **Never use Watts Water emails, drawings or specs.**
6. **Your baseline numbers.** For the Impact section I need your honest estimates: how many supplier emails a week at
   peak NPI; how many 7am/9pm calls a week; typical delay from one missed reply cycle (I assumed 24 h); share of
   supplier emails that are pure technical clarification (my guess is 40–60%; this is the key number in the
   stress test).
7. **GitHub:** public repo, or private + add `zlisto`? **Recommended: public**, since nothing secret is in it. Name
   suggestion: `supplier-whisperer`.
8. **Hosting:** **Recommended: local only** (zero-install clone + README). Hosting adds a 5-point risk if the free
   host sleeps.
14. **Live email (D2):** use the Gmail connector for the demo video? **Recommended: yes, as a stretch goal** (hike STEP 5
    builds it in dry-run; you flip real sending on yourself). Should TAs be able to email the live agent? If yes:
    **ask the professor first** (the course rule on extra keys), pre-allowlist `@yale.edu`, and announce a live window.
15. **Gmail account:** reuse `weideals25@gmail.com` with display name "John, Northfield Outdoor Labs", or create a new
    address that matches the persona? (Your call; creating accounts is something you do, not Claude.)

## 🟢 Nice-to-decide

9. Product name: "Supplier Whisperer" (your doc's working title). Keep it?
10. Demo defaults: Night mode + Medium risk. OK?
11. Demo video (optional backup, 2–3 min). **Recommended: yes**, record it Sunday from `demo_plan.md`. It protects
    the "it works" and "look + feel" points if staff hit trouble.
12. At **Medium** risk, should holding replies on commercial topics ("Wei will reply directly") auto-send? Right now they
    wait for you (they only auto-send at High). A supplier might value even a holding reply at 3am their afternoon.
13. ~~PydanticAI~~ **Recommendation changed (Sat): yes, for the 4 live model calls only.** The course's PydanticAI +
    Portkey path is proven with gpt-6-luna, while my urllib client is unverified. It's hike STEP 1, with urllib kept as a
    fallback. See `decisions.md` D1.

## Saturday evening (from the hike session)

1. **`MY_PERSONAL_EMAIL` is currently the agent's own address** (weideals25@gmail.com). Approve-by-email is
   therefore **off** (the agent never reads its own mail). To use it, set `MY_PERSONAL_EMAIL` to the address on your
   phone (e.g. your Yale address). Note this also allowlists that address as a "supplier" for testing, which is how it
   works today. **Recommended:** your Yale address.
2. **Fly.io:** ready to deploy when you have an account (`docs/deploy_fly.md`). Decide whether TAs may email the live
   agent (ask the professor first, course rule on extra keys). Never run the laptop mailbox and Fly at the same time.
3. **Report TODOs** need you: baseline numbers, the real-user quote, and the before/after turnaround
   (`docs/user_evidence.md`). They're marked as yellow TODO boxes in `docs/report_src.html`.
4. **REASONING_EFFORT=low?** Measured live: −15% cost per night, −22% output tokens, same outcome distribution
   (`docs/tokenomics.md`). Not switched on by default. **Recommended:** turn it on (`REASONING_EFFORT=low` in `.env`)
   after you read a few low-effort drafts.
5. **Email 2 (Lily, PCBA)** escalates in about 2 of 3 live runs (the live manager reads a timing question) but the demo
   script expects NEEDS_APPROVAL. Mock stays 9/9. Either accept it (it errs on the strict side) and say so in the
   demo, or reword sample email 2. I didn't change guardrails or sample data.
