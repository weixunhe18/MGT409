# Research notes: competitors, AgentMail, impact numbers (collected 2026-10-23)

Desk research by a research sub-agent, done overnight. Every claim has a source link. Items marked **UNVERIFIED**
could not be confirmed and should not go in the report as fact. Re-check any number before it goes into report.html.

## 1. AgentMail (agentmail.to), the infrastructure we build on, not against

- **What:** "the email inbox API for AI agents." API-created inboxes, threads, custom domains, webhooks and websockets, IMAP/SMTP, Python/TS SDKs, MCP server. https://www.agentmail.to/
- **Company:** YC Summer 2025, about 10 people, SF (https://www.ycombinator.com/companies/agentmail). $6M seed in March 2026 led by General Catalyst; more than 500 B2B customers (https://techcrunch.com/2026/03/10/agentmail-raises-6m-to-build-an-email-service-for-ai-agents/).
- **Pricing:** Free $0 (3 inboxes, 3k emails/mo) · Developer $20/mo (10 inboxes, 10k/mo) · Startup $200/mo (150 inboxes, 15k/day) · Enterprise custom. https://www.agentmail.to/pricing
- **Trust features they already have:**
  - Allowlists and blocklists for send, receive and reply, per inbox, pod or org. A blocked send returns `403 message_rejected`. https://docs.agentmail.to/lists.md
  - **Agent Armor** (Labs, free for now) scans **inbound** mail for prompt injection and returns a verdict of `clear` or `review`. Hold mode withholds the webhook. Self-described as "advisory, not a guarantee." Not available in the EU. https://docs.agentmail.to/agent-armor.md
  - Drafts and scheduled send. https://docs.agentmail.to/drafts.md
  - Human-in-the-loop is a *pattern* in their docs (drafts + labels + CC + allowlists), not a product. API keys can be limited to `draft_create` without `draft_send`. https://docs.agentmail.to/knowledge-base/human-in-the-loop.md, https://docs.agentmail.to/permissions.md
  - **Not found in their docs:** any check on outgoing content, i.e. whether a reply commits to price, quantity, dates or POs, or whether it attaches drawings. ("Not found" doesn't prove it doesn't exist.)
- **Webhook `message.received`** (our mock emails use this shape): https://docs.agentmail.to/api-reference/webhooks/events/message-received.md
  - Headers: `svix-id`, `svix-timestamp`, `svix-signature`
  - Body: `{type:"event", event_type, event_id, message, thread}`. `event_id` is stable across retries, so it can be used to drop duplicates.
  - `message`: `message_id, thread_id, inbox_id, from, to[], labels[], size, timestamp, created_at, updated_at`, plus optional `subject, text, html, extracted_text, cc, bcc, reply_to, in_reply_to, references, headers, attachments[], authentication_results, agent_armor`

## 2. Supplier and procurement AI competitors

| Company | What it does | Customer | Emails suppliers by itself? | Human review | Pricing |
|---|---|---|---|---|---|
| Didero | Agents across purchasing (POs, RFQs, follow-ups) on ERP and email; $30M Series A Feb 2026 (https://siliconangle.com/2026/02/12/didero-raises-30m-series-expand-agentic-ai-enterprise-procurement/) | Mid-market and enterprise manufacturers and distributors | Yes: RFQs and follow-ups | Routine tasks automatic, complex ones need approval | ~$250–$5,000 per workflow per month (Sacra estimate) |
| Leverage (tryleverage.ai) | PO follow-ups and acknowledgments, connected to ERP | Manufacturers and distributors | Implied | Not described | Not public |
| Pactum | Autonomous negotiation for indirect spend (https://pactum.com/) | Global 2000 | Negotiates on its own | "Your team makes the final call" | Typical customer has >$250M revenue |
| Keelvar | Agent-run sourcing events and bid optimization | Large enterprises | Engages suppliers | Humans approve awards | Not public |
| Fairmarkit | Agents for RFx (requests for quotes and proposals) | Enterprise | Not stated | Category managers lead | Not public |
| Arkestro | Predictive pricing and sourcing | Enterprise | Not stated | "Human where it matters" | Not public |
| Zip | Procurement orchestration from intake to payment | Startup to Fortune 500 | Not stated | Workflow engine | Not public |
| Levelpath | "Ranger," autonomous source-to-pay | Enterprise | Not stated | Configurable escalation | Not public |
| Lio | Agents for the full procurement workflow; a16z $30M Series A, YC S23 (https://techcrunch.com/2026/03/05/lio-ai-series-a-a16z-30m-raise-automate-enterprise-procurement/) | Global 2000 | Negotiates | Not stated | Not public |
| Mandel AI (YC S23) | Direct-materials purchasing from RFQ to invoice (https://www.ycombinator.com/companies/mandel-ai) | Manufacturers | Yes | Team approval rules | Not public |
| Lumari (YC Spring 2025) | RFQs, PO expediting, supplier communication (https://ycombinator.com/companies/lumari) | F500 to scale-ups | Yes, end-to-end | Configurable guardrails | Not public |
| **Waybill (YC S26)** | **Parts purchasing for deep-tech and hardware teams** (https://www.ycombinator.com/companies/waybill) | Hardware startups and defense | Requests quotes | Approvals routed | Not public |
| Kavida (acquired by QAD, Nov 2025) | Email-based PO and RFQ agent; "frees up to 50% of buyer time" (vendor claim) | Manufacturers | Handles date, quantity and price changes | Not stated | Not public |
| Tealbook | Supplier data, not communication (acquired by Supplier.io in April 2026) | Enterprise | No | n/a | n/a |

UNVERIFIED: "Reframe" (YC W26?) does "AI agents to automate hardware procurement"; couldn't find its YC page.

## 3. General-purpose AI email assistants

| Product | Why it doesn't solve this |
|---|---|
| Gmail Gemini | Help Me Write, suggested replies, summaries. No sending on its own, no supplier policy. |
| Copilot in Outlook (Agent mode, Apr 2026) | Sorts mail and drafts follow-ups for review. No overnight sending, no commitment controls. EchoLeak target. |
| Superhuman ($40/mo Business) | Auto Drafts that *you* review and send. Drafts only. |
| Fyxer | "Never sends emails… without your review." Doesn't help overnight. |
| **Lindy** | **Closest.** Can send on its own, with an "Ask for Confirmation" setting per action. But approval is all-or-nothing per action; it can't tell a reply that commits to price or dates from one that doesn't, and it doesn't read product docs. |
| ChatGPT agent / "ChatGPT Work" | General-purpose. Nothing supplier-specific (product status partly UNVERIFIED). |

## 4. Impact numbers

- **Time difference:** China is UTC+8 with no daylight saving. US Eastern is UTC−4 until Nov 1, 2026, then UTC−5. **The gap is 12 hours now and 13 hours from Nov 1.**
- **Engineer pay (BLS, May 2025 medians):** mechanical $104,110 ($50.05/hr); electrical/electronics $125,040; industrial $102,440. https://www.bls.gov/ooh/architecture-and-engineering/mechanical-engineers.htm
- **Email time:** knowledge workers spend 28% of the week (~13 h) on email (McKinsey 2012). https://www.mckinsey.com/industries/technology-media-and-telecommunications/our-insights/the-social-economy
- **Sourcing drag:** 86% of manufacturing leaders say sourcing parts takes time away from new product introduction (Fictiv 2025). https://www.fictiv.com/articles/fictivs-10th-annual-state-of-manufacturing-supply-chain-report-shows-an-industry-reeling-from-tariffs-and-economic-uncertainty
- **China share:** China supplied >90% of US laptop/monitor imports and >80% of smartphones before 2018; its share of all US imports fell from ~22% (2017) to ~9% (2025). https://www.piie.com/blogs/realtime-economics/2026/trump-china-trade-wars-five-takeaways-us-imports-2025
- **Cost of a late launch:** announcing a product delay cut market value by −5.25% on average (Hendricks & Singhal 1997, 101 firms). https://iaorifors.com/paper/22271
- **Response cycles:** practitioners say quotes take 24–48 h and each clarification costs "a full response cycle." This is practitioner evidence only, not research-grade. https://hardwaresecrets.com/lead-times-and-communication-with-a-china-cnc-supplier-what-to-expect/
- **Prompt injection:** OWASP LLM01:2025 says there is no known complete fix and recommends human review for privileged actions (https://genai.owasp.org/llmrisk/llm01-prompt-injection/). **EchoLeak** (CVE-2025-32711, CVSS 9.3) was a zero-click email attack that pulled data out of M365 Copilot (https://thehackernews.com/2025/06/zero-click-ai-vulnerability-exposes.html).
- **Avoid:** "15–35% of NPV" and "6 months late = 33% less profit." Both UNVERIFIED.

## 5. Stress test (the full version is in proposal.md)

1. *"AgentMail already sells your trust layer."* Their controls decide **who** the agent can talk to and **whether** it can send. Ours checks **what** a reply commits to and whether its answers come from your docs. We should build **on** AgentMail.
2. *"Funded vertical players already do this."* Most work **after** the PO, through ERP, and sell to buyers. Our wedge is the **engineering conversation before the PO** (DFM, spec questions) for engineers at startups with no ERP. Waybill and Lumari are the closest threats.
3. *"Once you block commitments, little is left to automate."* This is the hypothesis to test. We need pilot data on what share of supplier emails are answerable from the docs without a commitment.
