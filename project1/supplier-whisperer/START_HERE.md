# Start here (updated Sat Oct 24, evening)

**Status:** running on your Mac (Python 3.13, `.venv`). 107 tests, and 13/13 demo outcomes in **live gpt-6-luna** and
mock mode. Live mode needs no manual setup: the key is read from the repo-root `.env`, and `certifi` handles HTTPS.
The Gmail connector is built and tested with fake servers, but **not yet run against the real inbox** (it needs the
app password).

## Your next actions
1. Create a Google **app password** for weideals25@gmail.com and put `GMAIL_APP_PASSWORD=...` in the repo-root `.env`.
2. Run `python app.py --live --mailbox` (dry-run) and email it from your Yale address. Check the draft in the dashboard.
3. Set `MAILBOX_SEND=on` once the drafts look right. **Ask the professor before TAs use it** (course rule on extra keys).
4. Share the real Alibaba supplier threads; they'll be anonymized into `data/real_anonymized/` before any commit.

## What's in the folder

| File | What |
|---|---|
| `criteria.md` | The grading rubric from the course site, condensed, plus how we score on each line |
| `README.md` | How to run the app (one command), architecture, safety, datasets |
| `proposal.md` | Problem, solution, stack, architecture, safety, AgentMail stress test, rubric mapping |
| `demo_plan.md` | 4-minute demo script with the 13 sample emails + screenshot shot list |
| `weekend_plan.md` | Your checklists + paste-ready prompts for the hike (Sat 2 pm) and dinner (Sun 7 pm) sessions |
| `project_plan.md` | Ambitious roadmap, recommended technical path, business sketch, kill criteria |
| `decisions.md` | D1 PydanticAI (yes, live calls only) · D2 real email (Gmail connector, dry-run first) · D3 "John" persona · D4 how webhooks work |
| `assumptions.md` | Every call I made without you |
| `questions_for_morning.md` | Decisions only you can make |
| `research/competitors_and_impact.md` | Sourced competitor and impact research (AgentMail, Didero, Lindy, BLS, …) |
| `docs/user_evidence.md` | Template for your baseline numbers and the real-user session (needed for Impact points) |
| `app.py`, `supplier_agent/`, `tests/`, `scripts/` | The app |
| `data/sample/` | Fictional product spec, 13 supplier emails (AgentMail format), policy (allowlist etc.) |
