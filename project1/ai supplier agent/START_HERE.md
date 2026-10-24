# Start here (morning of Sat Oct 24)

**Status:** the MVP is built and verified (66/66 tests, 8/8 demo outcomes; now 9/9 after email 9 was added on Oct 24, dashboard clicked through end to end) in a
real Python 3.12 runtime inside Claude's sandboxed browser. This laptop has no Python, so nothing was installed here.
An independent review then found 13 issues, including a double-send race, script injection via a sender address,
and a kill switch that ignored in-flight emails. All are fixed and covered by tests.
**The live gpt-6-luna path has never been run.** Do that first.

> **On a new machine?** Claude's memory from the first session stays on the work laptop. Tell Claude Code:
> *"Read START_HERE.md and decisions.md first."*

## Your first 3 actions
1. Open `questions_for_morning.md` (3 blockers, ~10 decisions, each with a recommendation).
2. Get Python 3.12 running (personal machine recommended), then in this folder: `python app.py --test`, then
   `python app.py`, then click **▶ Run demo inbox**.
3. Put `PORTKEY_API_KEY` in `.env` one folder up and run `python app.py --demo --live --show-drafts`.

## What's in the folder

| File | What |
|---|---|
| `criteria.md` | The grading rubric from the course site, condensed, plus how we score on each line |
| `README.md` | How to run the app (one command), architecture, safety, datasets |
| `proposal.md` | Problem, solution, stack, architecture, safety, AgentMail stress test, rubric mapping |
| `demo_plan.md` | 4-minute demo script with the 9 sample emails + screenshot shot list |
| `weekend_plan.md` | Your checklists + paste-ready prompts for the hike (Sat 2 pm) and dinner (Sun 7 pm) sessions |
| `project_plan.md` | Ambitious roadmap, recommended technical path, business sketch, kill criteria |
| `decisions.md` | D1 PydanticAI (yes, live calls only) · D2 real email (Gmail connector, dry-run first) · D3 "John" persona · D4 how webhooks work |
| `assumptions.md` | Every call I made without you |
| `questions_for_morning.md` | Decisions only you can make |
| `research/competitors_and_impact.md` | Sourced competitor and impact research (AgentMail, Didero, Lindy, BLS, …) |
| `docs/user_evidence.md` | Template for your baseline numbers and the real-user session (needed for Impact points) |
| `app.py`, `supplier_agent/`, `tests/`, `scripts/` | The app |
| `data/sample/` | Fictional product spec, 9 supplier emails (AgentMail format), policy (allowlist etc.) |
