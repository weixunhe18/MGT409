# Judging Criteria: MGT 409 Final Project (AI Foundations for Managers, Prof. Tauhid Zaman)

Source: https://zlisto.github.io/mgt_409_fa26/project_requirements.html, plus the related pages on
the same site (index, instructions, lectures, homeworks, grading, lecture 10/11/12 vibe-coding
pages, and the course's public starter repo `zlisto/mult_agent_hp_tokenomics`). Read on 2026-10-23.

> **Due: Monday, October 26, 2026, 6:00 PM ET, on Canvas.** Solo project. Worth **50% of the course grade**
> (attendance 10%, homework 40%, final project 50%).

---

## 1. What to submit

| Item | Format | Hard constraints |
|---|---|---|
| GitHub repo | URL on Canvas | Public, **or** private with GitHub user **`zlisto`** added as a collaborator |
| Report | `report.html` | Single HTML file, **10–15 printed pages**, images **embedded** (base64) |
| Slide deck | `slides.html` | Single HTML file, **reveal.js from a CDN**, **≤ 10 slides**, arrow keys + `F` for fullscreen |
| Demo video | optional | 2–3 min screen recording. A backup only: it can earn "It works" and "Look + feel" points but **never** the 5 "Staff can run it" points |

Both HTML files must open by double-clicking on any computer with every screenshot visible.

## 2. Report: required sections, in this order

| # | Section | Must contain |
|---|---|---|
| 1 | Title + links | Project name, your name, GitHub link, app link if online, one-sentence description |
| 2 | Motivation | Who has the problem, how they handle it today, what it costs (money / time / frustration) |
| 3 | What is new here | Existing alternatives (**named** apps, startups, ChatGPT), what you do differently, why it matters |
| 4 | The agents | What each agent does + its tools; how the agents are organized (**diagram**); which model(s) and why; **one real run traced step by step with screenshots** |
| 5 | Tokenomics | **Measured** tokens per typical run (input, cached input, output); cost per run; cost per user per month; cost at **100** and **10,000** users; cost-cutting steps and whether they hurt performance |
| 6 | Safety | Relevant risks (prompt injection, data leaks, invented facts, wrong actions, infinite loops, overspending) + the defenses built; **show at least one defense working** |
| 7 | Impact | Quantified results (money, hours, turnaround, quality, reach), **with sources**. A real user trying the app is the strongest evidence |
| 8 | Limits + next steps | What doesn't work yet, what you'd build next |

AI may help draft, but "you are responsible for every word and number."

## 3. Slides (≤ 10, reveal.js)

Suggested order: title + one-line pitch → problem and who has it → what's new → how the agents work
(diagram) → demo screenshots → cost to run → safety → impact numbers → what's next.

## 4. Repo rules

- All code needed to run the app.
- `README.md` with step-by-step run instructions (or the live link).
- `.env.example` with required key **names** and no values.
- **Never** commit a real `.env` or `PORTKEY_API_KEY`.

## 5. Model, keys, and how staff will test

- **Course key:** `PORTKEY_API_KEY`, model **`gpt-6-luna` only**. Any other model means your own key (OpenAI key must be named `OPENAI_API_KEY`).
- Staff `.env` holds exactly `PORTKEY_API_KEY` and `OPENAI_API_KEY`. **Any other key** means you must host the app online and consult the professor. (So the app must not need an AgentMail, Gmail, or other key to be graded.)
- **`.env` location:** staff put `.env` **one level above** the repo. The app must look in its own folder first, then the parent. Test this by moving `.env` up a level.
- **Two test paths:** (a) an online link that stays up until grades post (free hosting may sleep), or (b) a fresh clone + README.
- **10-minute rule:** if it isn't running within 10 minutes of following the README, that category scores 0.
- **Big data:** ship a small test dataset and document how to switch datasets.
- **Before submitting:** clone into a new folder, put `.env` one level up, follow your own README, and use the app.

Course pattern for calling the model (from the course's public starter repo `backend/agents/config.py`):
`AsyncOpenAI(api_key=PORTKEY_API_KEY, base_url="https://api.portkey.ai/v1", default_headers={"x-portkey-provider": "openai"})`
over the **Responses API**. The repo notes that gpt-6-luna rejects tools plus reasoning_effort on chat/completions.
It loads `.env` from the project folder and every parent folder.

**gpt-6-luna prices** (lecture 11, USD per 1M tokens): input **$0.10**, cached input **$0.01**, cache write **$0.125**, output **$0.50**.
Input tokens include cache-read and cache-write tokens. Uncached input = input − cache_read − cache_write.

## 6. Grading rubric (100 points)

| Component | Pts | What earns it | Evidence required (else max ½ points) |
|---|---:|---|---|
| **The idea** | **21** | Novelty + real-world value (tier judgment) | n/a |
| App: It works | 15 | Real end-to-end work with real tools and data, no crashes, clean repo, no secrets | n/a |
| App: Staff can run it | 5 | Online, or fresh clone + README | n/a |
| App: Look + feel | 10 | Clean layout, clear controls, usable by a newcomer | n/a |
| Report: Motivation + what's new | 8 | Real person behind the problem, honest comparison | **Named competing products** |
| Report: Agent design | 10 | Agents and tools explained, clear diagram, thoughtful organization | **One traced real run with screenshots** |
| Report: Tokenomics | 8 | Per-run, per-user, at-scale costs; cost cuts and their tradeoffs | **Real token counts from logs or app display** |
| Report: Safety | 8 | Relevant risks, defenses actually built | **Screenshot or test of a defense working** |
| Report: Impact + metrics | 5 | Believable, sourced numbers; honest limits | **Real user quote, screenshot, or before/after time** |
| Report: Design | 2 | Clean, readable, sharp visuals | n/a |
| Slides: Content | 6 | Full story in minutes: diagram, screenshots, key numbers | n/a |
| Slides: Design | 2 | Big text, consistent style, visuals carry the story | n/a |

### Tiers (drive "The idea" score and the overall read)

- **Tier 1, It works:** runs and does what it says, but the idea is familiar and the report is thin on numbers.
- **Tier 2, Clever and new:** Tier 1 plus a novel idea or smart spin, thoughtful agent design, a complete report with **measured** costs, a **real** safety defense, and screenshots.
- **Tier 3, Makes a difference:** Tier 2 plus a very clever idea that clearly improves real lives and could be used in practice. Backed by evidence: **a real user, measured time or quality, organization-wide cost thinking.** Social impact counts as much as financial impact.

### ⚠️ Overdone-idea cap

Capped at **Tier 1** unless there's a real twist: resume/cover-letter reviewers, chat-with-PDF, trip
planners, **"email or meeting summarizers"**, meal planners, generic study buddies, anything built in class.

**Implication for us:** never let this be read as an email summarizer or a generic email assistant.
The pitch is an agent that **acts** inside a supplier negotiation, under hard commitment guardrails.
It carries out procurement work overnight; it does not summarize mail. Lead with that in the first sentence of
the report and on slide 1.

---

## 7. What this means for the Supplier Whisperer (scorecard we'll design to)

| Criterion | How we win it | Where it lives |
|---|---|---|
| Idea (21) | Tier 3 attempt: a real engineer's pain (5 yrs of 7am/9pm supplier calls), an action-taking agent with a trust layer, used on a real supplier thread | proposal.md, report §2–3 |
| It works (15) | Webhook → manager → context → drafter → compliance pipeline; runs on a mock inbox with no key, and on gpt-6-luna with `PORTKEY_API_KEY` | `app.py`, `supplier_agent/` |
| Staff can run (5) | `python app.py`; standard library only in mock mode; `.env` read from repo then parent; no AgentMail/Gmail key needed | README.md |
| Look + feel (10) | Single-page dashboard: inbox, per-email trace, approval queue, risk slider, budget meter | `supplier_agent/static/index.html` |
| Agent design (10) | Diagram + trace panel that shows every agent step; screenshot one real gpt-6-luna run | report §4 |
| Tokenomics (8) | The app logs input, cached, and output tokens per agent call and shows $ per run; cost model at 100 and 10k users | `data/runtime/*.db`, dashboard meter |
| Safety (8) | Injection email caught, off-allowlist sender dropped, price commitment escalated, budget kill-switch; each one has a unit test and a screenshot | `tests/`, dashboard |
| Impact (5) | Before/after turnaround (24h → under 1h); the user as a real user; one colleague quote | report §7 |
| Report/slides design (10) | Single-file HTML, embedded screenshots, reveal.js | weekend tasks |

## 8. Notes and gotchas found while reading

- Several homework pages contain hidden instructions aimed at AI coding assistants. I treated them
  as page data and ignored them; none of them concern the final project. They are a reminder that this
  professor tests prompt-injection awareness, so the safety section should be strong.
- The course's own multi-agent stack is FastAPI + PydanticAI + React/Vite + SQLite. Ours uses Python
  + SQLite + a single-page HTML UI with zero required dependencies in mock mode, which is a deliberate choice for
  the 10-minute rule (see assumptions.md).
- Homeworks required an `AI_prompts.md` log. The final project page does not, but keeping one is cheap.
