# Supplier Whisperer: Project plan, roadmap and recommended technical path

**Ambition:** become the **trusted night-shift colleague for every hardware engineer who works with overseas
suppliers**. It closes routine engineering loops while the team sleeps, and it never commits the company to
anything a human didn't approve.

**North-star metric:** *engineering days saved per NPI program*: clarification cycles closed overnight instead of
next day, with **zero unapproved commitments** as a hard constraint (any bad commitment counts as an incident).

**The hypothesis that decides everything:** a large enough share of supplier emails (≥ 30–40%) during DFM/EVT/DVT
can be answered from the spec **without committing to price, quantity, dates or POs**. If the pilot shows < 20%, pivot
to "overnight triage + morning brief" (still valuable, but a smaller product).

---

## Roadmap

### Phase 0: Class MVP (done this weekend, Oct 24–26)
- Webhook pipeline (manager → context → email → compliance) on a mock AgentMail inbox; deterministic trust layer;
  dashboard; 66 tests; live gpt-6-luna path; report and slides.
- **Weekend decisions** (`decisions.md`): PydanticAI for the 4 live model calls (orchestration stays code); persona
  "John, Supply Chain" that never claims to be human; **live Gmail connector** (IMAP polling + SMTP, works on a laptop,
  no public URL) built in dry-run, used for the demo video. The mock inbox stays the graded path.

### Phase 0.5: Live mailbox hardening (before any real supplier sees it)
| Must-have | Why |
|---|---|
| DKIM/DMARC check on allowlisted senders (`Authentication-Results`) | `From:` is trivially spoofed; without this the allowlist is bypassable |
| Reply only to the authenticated `From`, never `Reply-To` | Attackers redirect replies through `Reply-To` |
| Per-sender and global daily send caps + an outbound kill switch | Limits damage from a bug or a loop |
| Threading headers (`In-Reply-To`, `References`) | Replies land in the supplier's existing thread |
| `MAILBOX_SEND=dry-run` by default; flipped only by Wei | Nothing leaves the building until you decide |

### Phase 1: Real pilot on your own threads (Nov–Dec 2026)
| Feature | Why | Done when |
|---|---|---|
| **Real inbox via AgentMail**: a dedicated address (e.g. `wei-assistant@yourdomain`) that suppliers CC, or a forwarding rule from Gmail | Real traffic without handing over your whole mailbox | Webhook receives real mail; Svix verified with the real secret |
| **Shadow mode**: the agent drafts and decides but never sends; you compare its decision with what you actually did | Builds the evidence before any autonomy | 4 weeks of shadow data |
| **Eval harness**: 50–100 anonymized real threads with gold labels (answerable? which topics? correct answer?) run in CI | Turns "trust me" into numbers; catches regressions from prompt or model changes | `make eval` reports commitment-leak rate (**must be 0**), escalation precision/recall, answer accuracy, auto-send rate |
| **Mobile approvals**: push or Slack with Approve / Edit / Escalate buttons | Turns 9–5 supervision into 30-second taps | p50 approval time < 2 min |
| **Feedback → policy**: 👍/👎 notes become few-shot examples and new regex rules, reviewed by you | The agent learns your style and risk appetite | Weekly policy diff |

### Phase 2: Trust and language (Q1 2027)
- **Bilingual drafting** (Chinese ↔ English) with a *back-translation check*: draft in Chinese, translate back,
  and run the compliance checks on both versions.
- **Attachment understanding in a sandbox**: quotes, FAI reports and DFM PDFs are parsed into **structured data
  only** (tables and numbers, never instructions). This closes today's biggest blind spot.
- **Per-supplier policies**: trust levels, topics allowed per supplier, quiet hours in *their* time zone.
- **Email authentication signals**: use AgentMail `authentication_results` (SPF/DKIM/DMARC) and the Agent Armor
  verdict as extra inputs to the sender gate.
- **Secure drawing release**: after human approval, the agent can send an *expiring portal link*, never an attachment.

### Phase 3: Workflow depth (Q2 2027)
- **Spec sources**: read requirements from where they live (Notion/Confluence, Onshape/SolidWorks PDM metadata,
  Arena/OpenBOM), with section-level SHAREABLE/CONFIDENTIAL labels managed in the UI.
- **Engineering change workflow**: a supplier's substitute-part proposal becomes a structured ECR draft for you.
- **Quote normalization**: incoming quotes become a comparison table (read-only; the agent still never negotiates).
- **WeChat Work / WhatsApp channel** for quick updates, using the same policy engine.
- **Supplier responsiveness analytics**: who answers fast, who slips; feeds sourcing decisions.

### Phase 4: Team product (H2 2027)
- Multi-user orgs, SSO, role-based approvals (engineer vs. supply-chain manager vs. finance for anything payment-related).
- **Audit log** of every draft, decision, override and send (immutable), plus exportable compliance reports.
- An **org policy library** ("never mention launch dates", "drawings only via portal") shared across teams.
- SOC 2 readiness, data residency options, BYO-model (Azure OpenAI / Bedrock) for enterprises.

---

## Recommended technical path

**Principle: keep the brain small and the guardrails in code.** The MVP's architecture is the right one: the
orchestration is deterministic, the LLM agents produce narrow JSON, and only code can send.

| Area | Now (MVP) | Recommended next | Why |
|---|---|---|---|
| Email | Mock AgentMail webhook + mock outbox; Gmail IMAP/SMTP connector for the class demo (dry-run first) | **AgentMail** with **two API keys**: the agent's key can only `draft_create`; the **policy service** holds the only `draft_send` key | Enforces "only code can send" at the infrastructure level. AgentMail documents exactly this permission split. Their allowlists and Agent Armor become layer 0. |
| Runtime | stdlib `http.server`, 1 worker thread | **FastAPI** + a durable queue (Postgres-backed jobs or Redis/RQ), idempotent workers keyed on `event_id` | Webhooks retry; jobs must survive restarts; idempotency prevents double replies |
| Storage | SQLite | **Postgres** (runs, trace, outbox, policies, evals) + encrypted blob store for raw mail | Multi-user, audit, backups |
| Agents | Hand-rolled JSON calls (manager/context/drafter/compliance) | **Decided: PydanticAI** leaf agents with Pydantic output models on the course's Portkey/Responses path; no side-effecting tools; add tracing (Logfire/OpenTelemetry or Portkey logs) | Proven gpt-6-luna path, validated outputs with retries, per-agent usage; safety stays in code |
| Models | gpt-6-luna for everything | **Route by task**: cheap model for triage and compliance; stronger model for Chinese drafting and long threads; pick per eval results, not vibes | Cost/quality trade-off backed by data; prompt caching for the spec prefix |
| Retrieval | Whole shareable spec in the prompt (small) | Section-chunked spec + embeddings once specs exceed ~20k tokens; always keep "number must exist in the source" grounding | Scales to real PRDs without losing the anti-hallucination guarantee |
| Safety | Regex/HTML injection gate, 11 outbound checks, budget caps, kill switch | Add a **red-team corpus** (hundreds of injection variants, incl. Chinese and Unicode tricks) to CI; canary tokens in confidential docs; rate limits per sender; anomaly alerts (sudden topic or volume shift) | OWASP LLM01 says there's no complete fix, so defense in depth plus continuous testing |
| UI | Single HTML page | Same design, componentized (React or HTMX), plus a mobile approval view | Keep the trust UX: trace, evidence, one-tap approve |
| Hosting | Local | Fly.io or Render with a managed Postgres; secrets in a vault; webhook behind HTTPS | Webhooks need a public HTTPS endpoint |

### Build order for the first 6 weeks after submission
1. **Week 1:** AgentMail inbox in *shadow mode* (drafts only) + Postgres + a durable queue.
2. **Week 2:** Eval harness and gold set from 50 anonymized real threads; CI gate `commitment_leaks == 0`.
3. **Week 3:** Slack/mobile approvals; morning brief as a scheduled 8:45 am message.
4. **Week 4:** Chinese drafting with a back-translation check; per-supplier quiet hours.
5. **Week 5:** Sandboxed PDF quote/FAI extraction (structured data only).
6. **Week 6:** Turn on autonomy for **one** supplier at **Medium** risk; review weekly.

---

## Business sketch (for the "could be used in practice" story)

- **Who pays:** hardware startups and small hardware teams (5–200 people) with 3–20 overseas suppliers and no
  procurement department. The first users are engineers, the buyer is the head of hardware or operations.
- **Pricing hypothesis:** $49–99 per engineer per month. At the measured model cost (well under $5 per user per month)
  plus email infrastructure, gross margin is > 85%.
- **Go-to-market:** hardware founder communities, YC hardware batch companies, contract-manufacturer partners who
  benefit from faster answers (they could even recommend it).
- **Expansion:** engineering Q&A → change requests → quote comparison → procurement workflows (where Didero, Lio
  and Lumari play). The trust track record is the wedge.

## Risks and kill criteria

| Risk | Signal | Response |
|---|---|---|
| Too few emails are safely answerable | Pilot auto-answerable share < 20% | Pivot to triage + morning brief + one-tap replies |
| A bad commitment goes out | Any incident | Stop autonomy globally, post-mortem, add an eval case before re-enabling |
| A supplier discovers "John" is automated and feels misled | Direct "are you a bot?" questions; colder tone | Identity questions already escalate to Wei. Decide a disclosure policy per supplier; if you productize, add disclosure for EU users (EU AI Act transparency rules apply from Aug 2026) |
| Suppliers dislike the replies | Negative replies, slower responses | Tune tone with 👍/👎 feedback; keep the agent on drafts-only for that supplier |
| Platform risk (AgentMail or the big email AIs add commitment rules) | Feature announcements | Stay vertical: spec grounding, supplier policies, NPI workflow and eval data are the moat |
| Confidential-data concerns | Security reviews block adoption | Data minimization (already built), BYO model, on-prem option, SOC 2 |
