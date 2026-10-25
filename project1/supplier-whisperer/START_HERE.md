# Start here (final, Sun Oct 25)

**Status:** submission-ready. 114 tests pass; the 13-email demo matches every expected outcome in mock and live
gpt-6-luna; a fresh clone from GitHub, with `.env` one level above the repo (the staff layout), ran the live demo in
46 seconds.

## Submit on Canvas (by Mon Oct 26, 6:00 PM ET)

1. **GitHub repo link:** `https://github.com/weixunhe18/MGT409` (public). The root README points to this project.
   This is the same link as in the report's title block.
2. **`report.html`:** `project1/supplier-whisperer/report.html` (13 printed pages, images embedded).
   Download it from GitHub (or take it from this folder) and upload the file itself.
3. **`slides.html`:** `project1/supplier-whisperer/slides.html` (10 slides, reveal.js; arrow keys, F for fullscreen).
4. **Demo video (optional):** `project1/supplier-whisperer/docs/demo_video.mp4` (2.5 min, narrated by macOS text-to-
   speech, recorded from the real app). If you prefer your own voice, play the video muted and narrate over it, or
   re-record with `scripts/record_demo.py`.

Before you upload, double-click `report.html` and `slides.html` once and click through the slides.

## What's in the folder

| File | What |
|---|---|
| `README.md` | How to run (one command), architecture, safety, Gmail mailbox, scorecard |
| `report.html`, `slides.html` | The deliverables (built from `docs/report_src.html` and `docs/slides_src.html` with `scripts/inline_images.py`) |
| `docs/demo_video.mp4` | Narrated demo video |
| `decisions.md` | D1–D10: every product and safety decision with its trade-off |
| `docs/tokenomics.md` | Measured tokens and cost per agent, per email, per user, at scale |
| `docs/user_evidence.md` | Your baseline, the tester quote and the 3-week payment story |
| `docs/deploy_fly.md` | How to put the Gmail mailbox on Fly.io later (not deployed) |
| `criteria.md` | The rubric, condensed |
| `proposal.md`, `weekend_plan.md`, `questions_for_morning.md`, `assumptions.md` | Planning history (not graded) |

## Kept private (never committed)

`data/raw_private/` (git-ignored): the two real supplier threads, the PRD, and every replay result. Only aggregate
numbers appear in the report.

## If you have 10 more minutes

- Optional live-email demo for TAs: ask the professor first (course rule on extra keys), then see README "Live mailbox".
