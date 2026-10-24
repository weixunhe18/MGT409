# Decisions and trade-offs (Sat Oct 24)

A record of the product and technical calls, with the reasoning. The report's "agent design" and "safety"
sections can quote from this.

---

## D1. PydanticAI for the model calls? **Yes, for the 4 live LLM calls only (do it on the personal machine)**

**What it would replace:** `supplier_agent/llm.py` (a hand-written urllib call to Portkey's Responses API) and the
hand-parsed JSON in `agents.py`. **What it must not replace:** the deterministic orchestration and guardrails.

| Benefit | Why it matters here |
|---|---|
| **A known-good gpt-6-luna path** | The course's `build_model()` (`OpenAIResponsesModel` + Portkey + `x-portkey-provider: openai`) is proven in class. My urllib client is the **single biggest unverified piece** of the app. This alone justifies the switch. |
| **Typed outputs with automatic retries** | `output_type=Triage` (a Pydantic model) is validated. If the model returns malformed JSON, PydanticAI re-asks it. Today a bad JSON reply means "fail closed → escalate", which is safe but causes needless escalations. |
| **Consistent token accounting** | `result.usage()` gives input / output / cache-read / cache-write tokens, the exact fields in lecture 11's cost formula, which feeds Tokenomics. |
| **Grader familiarity** | The rubric asks for "what each agent does and what tools it uses." Agents with typed outputs (and, optionally, a `lookup_spec(section)` tool on the context agent) read as thoughtful agent design to graders who wrote HW4–6. |
| **Test doubles** | `FunctionModel`/`TestModel` replace my `ScriptedLLM`. |

| Cost / risk | Mitigation |
|---|---|
| "Nothing to install" goes away | Run `pip install -r requirements.txt` (one line, about a minute, the course norm). **Import pydantic_ai lazily, only in live mode**, so `--mock`, `--demo` and `--test` still run on bare Python. |
| Version drift | Pin `pydantic-ai-slim[openai]` to the version that works on Saturday. |
| Temptation to let a "boss agent" call `send_email` | **Don't.** Every PydanticAI agent is a leaf with no side-effecting tools. Code alone decides and sends. This is the core safety claim. |

**Plan:** this is hike-session STEP 1 (see `weekend_plan.md`). Keep the urllib client behind `LLM_CLIENT=urllib` as a
fallback until the PydanticAI path passes the live demo. About 1–1.5 h of Claude Code time.

---

## D2. Real email, so a TA can talk to the agent from their own inbox

### Can it send and receive if hosted locally? **Yes, if receiving is *pulled*, not *pushed*.**

- **Sending** is an outbound connection (SMTP or an email API), so it works from any laptop.
- **Receiving by webhook** (the provider calls *your* URL) does **not** work on `127.0.0.1`: the internet can't
  reach your laptop. You'd need hosting or a tunnel (ngrok / cloudflared).
- **Receiving by polling works locally:** IMAP every 30–60 s (Gmail), or AgentMail's API/WebSocket. No public URL.
- **The catch:** it only answers while your machine is on and the app is running. Mail that arrives while the laptop is
  off **waits in the inbox** and is answered when you restart. Nothing is lost, but it's not "overnight" unless the
  machine stays on.

### Which mailbox

| | **Gmail account** (e.g. `weideals25@gmail.com`, display name "John, Northfield Outdoor Labs") via IMAP + SMTP | **AgentMail inbox** via API |
|---|---|---|
| Looks like a person | ✅ | ⚠️ `…@agentmail.to` unless you buy a custom domain |
| Setup | 2-Step Verification + an **app password** (verify Google still allows this for your account) | Free account + API key |
| Receive on a laptop | IMAP polling, no public URL | API polling or WebSocket; webhooks need a public URL |
| Code | stdlib `imaplib` / `smtplib`, ~200 lines | stdlib urllib to REST; our webhook handler already speaks its format |
| Story | "plugs into any mailbox" | "built on AgentMail" (matches the proposal) |

**Recommendation:** use the **Gmail connector for the class demo** (it looks human, which fits D3, needs no hosting, and
uses no new libraries). Put **AgentMail on the product roadmap**. Keep the **mock inbox as the default graded path**.

### How the TA reaches it without creating anything

- ⚠️ **Course rule:** staff only have `PORTKEY_API_KEY` and `OPENAI_API_KEY`; "any other key requires putting the app
  online and consulting the professor." A Gmail app password is another key. So the **graded path stays mock**,
  and the live-email round trip is shown **in your demo video**. If you want TAs to email it live, **ask the professor
  first**, and the app must be running when they write.
- **No self-service allowlisting on a public page.** An allowlist that anyone can edit isn't an allowlist, and the
  dashboard has no login. Instead:
  1. **Pre-allowlist `@yale.edu`** (domain entry, demo-only, rate-limited to about 10 replies per sender per day). A TA
     writing from a Yale address gets an answer with zero setup.
  2. **Any other address lands in HELD.** You click "Add to allowlist & re-run" in your dashboard. This makes a great
     live human-in-the-loop moment.
  3. Optional: a **pairing code**, shared privately in the Canvas submission comment (never in the public README),
     in the subject line auto-allowlists that sender for 48 h.
- **Uptime:** free hosting tiers sleep, so a poller stops. Realistic options are a stated live window ("online
  Mon 9–5 ET") on your machine, a ~$5/month always-on VM (money, so your call), or a GitHub Actions cron that polls every
  10 min (free but clunky).

### Safety work required before any real send (built Sat Oct 24, `supplier_agent/mailbox.py`)
1. **Anti-spoofing:** anyone can forge `From: kevin.zhang@hongyuan-mold.example`. For allowlisted senders, require
   `dkim=pass` / `dmarc=pass` in Gmail's `Authentication-Results` header (or AgentMail's `authentication_results`);
   otherwise treat the sender as unknown.
2. **Reply only to the authenticated `From`**, never to `Reply-To` (attackers set it to redirect replies).
3. Per-sender and global **daily send caps**, plus a separate **outbound kill switch**.
4. Proper threading headers (`In-Reply-To`, `References`) so replies stay in the supplier's thread.
5. A **dry-run flag that defaults to ON**: drafts appear in the dashboard but nothing is sent until you flip it.

---

## D3. AI disclosure → **persona "John, Supply Chain, Northfield Outdoor Labs"** (done)

- Replies are now signed:
  ```
  John
  Supply Chain, Northfield Outdoor Labs
  ```
  Configure it in `data/sample/policy.json` (`persona` + `assistant_signature`). The drafter writes as John and
  never mentions AI.
- **Kept: it never claims to be human.** If a supplier asks "are you a bot / a real person?", that's a new hard topic
  (`identity`). The email is **escalated to you**, never auto-answered even at High risk, and the holding draft
  doesn't mention it. The compliance reviewer also flags any draft that claims to be human. Two tests cover this.
- **Why this middle path:** you get the natural tone you want. You decide personally what to say if someone asks
  directly, so the system never lies on its own.
- **Trade-offs to note in the report:**
  - **Pro:** a natural relationship; suppliers don't try to game a bot.
  - **Con:** if a supplier finds out, it can damage trust. Supplier relationships in China lean heavily on personal trust.
  - **Regulation (not legal advice):** the EU AI Act's transparency duty for AI that talks to people applies from
    Aug 2, 2026 to systems used in the EU. That's not your US–China setup today, but it matters if you productize or
    work with EU suppliers. US bot-disclosure laws such as California's are narrow (sales and election bots on large
    platforms), so they're likely not relevant.
  - **For graders:** state the persona choice and the identity guardrail openly in the Safety section. Transparency
    with graders scores better than hoping they don't notice.

---

## D4. How the webhook works, and do you need an API key?

**A webhook is the email provider calling your app** with an HTTP POST the moment mail arrives, instead of your app
asking every minute.

1. A supplier emails the agent's inbox.
2. The provider (AgentMail) POSTs a JSON event to your registered URL: `event_type: "message.received"`, with
   `from`, `subject`, `text`, `thread_id`, …
3. It signs the request with a secret only you and it know (Svix headers `svix-id`, `svix-timestamp`,
   `svix-signature`). Your app recomputes the signature and **rejects anything unsigned, altered or older than 5 min**.
4. Your app replies `200` immediately and processes the email in the background. If it doesn't reply, the provider
   retries, which is why we drop duplicates by `message_id`.

| Situation | Keys needed |
|---|---|
| **Today (mock inbox)** | **None.** The "Run demo inbox" button and `scripts/send_test_webhook.py` play AgentMail's role and sign with a built-in dev secret. `/webhook/agentmail` is real, tested code. |
| **Real AgentMail** | (1) AgentMail **API key** (create the inbox, register the webhook, send replies); (2) the webhook's **signing secret** `whsec_…` → `WEBHOOK_SECRET` in `.env`; (3) a **public HTTPS URL** (hosting, or a tunnel while your laptop runs). |
| **Gmail (D2 recommendation)** | **No webhook at all.** IMAP polling plus an **app password**. (Gmail's push option needs a Google Cloud Pub/Sub project and a public endpoint, which is overkill here.) |

Cost note: webhooks and polling both keep the agents idle until mail arrives. Checking IMAP every 60 s uses zero
LLM tokens.

---

## D5. Every engineering-change proposal waits for Wei, even when the spec already settles it (decided Sat)

- **What happened:** the first live run held emails 1 ("can we use P20 steel?") and 8 ("ultrasonic welding instead of
  adhesive?") for approval, while the demo script expected them to auto-send. The spec answers both, but each is a
  supplier *proposing* a process change.
- **Decision:** keep the hold. Any proposed part, material or process change produces a draft for approval, never an
  automatic reply. The mock triage regex now also catches "can we use…" and "…instead of…", so mock and live agree.
- **Demo impact:** emails 1 and 8 are now expected NEEDS_APPROVAL. **Email 9** (routine gate, gasket and finish
  questions) was added as the auto-send example.
- **Trade-off:** suppliers wait a few hours longer on change questions that the spec already answers. In return the agent
  never approves a change on its own: a spec line can be outdated, and changes are where the expensive mistakes happen.

---

## D6. Holding replies auto-send at Medium risk (decided Sat)

- **Before:** when a decision waits on Wei (price, quantity, dates, POs, drawings), the holding reply ("Wei will
  review this and reply directly") was only sent automatically at High risk. At Medium it waited for approval.
- **Now:** at Medium and High, at night, the supplier gets the holding reply right away, so they know someone is on it.
  The decision itself still always comes from Wei.
- **Unchanged guards:** the holding reply must pass every deterministic compliance check (no numbers, no commitment
  verbs). It is never sent if any soft warning fired (injection suspicion, reviewer flag, loop guard), or for
  "are you a bot?" questions. Low risk and business hours still make everything wait.
- **Trade-off:** a supplier may read a quick holding reply as "yes is coming". The wording promises only a review.

---

## D7. Always-on hosting: Fly.io, IMAP polling, no public endpoint (decided Sat)

- **Why always-on:** the mailbox only answers while the app runs. A laptop sleeps; a ~$2/month Fly.io machine doesn't,
  so suppliers really get answers at 3 am ET.
- **Why polling, not webhooks:** Gmail push needs a Google Cloud Pub/Sub topic, a `users.watch` call renewed at
  least every 7 days, and a public HTTPS endpoint that has to authenticate Google's pushes. IMAP polling every 60 s
  is one outbound connection: no public endpoint, nothing to renew, and it costs zero tokens while idle. A 60 s delay
  doesn't matter against a 12 h time-zone gap.
- **Why no public port:** the dashboard has no login. `fly.toml` defines no `[http_service]`/`[[services]]`, and the
  new `--fly-private` flag binds only Fly's private `fdaa::/16` address (refused anywhere else). Wei opens the
  dashboard with `fly proxy 8000`. Steps: `docs/deploy_fly.md`.
- **Trade-off:** no public link for graders (they use the mock inbox from a fresh clone, as before), and a second
  poller (laptop + Fly) would double-reply, so only one may run at a time.
