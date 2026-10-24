# Tokenomics: measured on live gpt-6-luna (Portkey)

Measured 2026-10-24 18:06 UTC with `python scripts/measure_tokens.py`. Raw per-call data: `docs/tokenomics.json`. Prices (lecture 11, per 1M tokens): input $0.10, cached input $0.01, cache write $0.125, output $0.50. Reasoning tokens are billed as output and are included in output.

Setup: the 9-email sample inbox, Night mode, Medium risk, a fresh in-memory store per run, 3 runs at the default reasoning effort. Expected outcomes matched per run: 8/9, 9/9, 8/9.

**Portkey cache check.** Earlier repeated runs showed identical token counts. That was Portkey's response cache: the app now logs Portkey's `x-portkey-cache-status` header per call, and ordinary repeat runs of the demo inbox came back `HIT` on every model call (same answer, same token counts, returned in about 1 s instead of 2–5 s). A tiny two-call probe had shown `MISS`, so the cache only shows up on real, repeated prompts. For this measurement every call sent `x-portkey-cache-force-refresh: true` (the app's new `PORTKEY_CACHE=refresh` setting), and the header read REFRESH on every call: these are fresh model answers. Input counts are still nearly identical run to run because the prompts are identical; output counts vary.

## Per agent (mean per call, default effort)

| Agent | Calls / night | Input | Cached | Output (of which reasoning) | $ per call | Latency |
|---|---:|---:|---:|---:|---:|---:|
| manager | 6.0 | 648 | 0 | 323 (102) | $0.000226 | 4.2 s |
| context | 4.0 | 1,550 | 1,349 | 205 (70) | $0.000141 | 3.4 s |
| drafter | 6.0 | 777 | 0 | 266 (179) | $0.000211 | 4.0 s |
| compliance | 6.0 | 698 | 0 | 132 (114) | $0.000136 | 3.2 s |

## Per email type (mean, default effort)

| Outcome | Emails measured | $ per email |
|---|---:|---:|
| AUTO_SENT | 3 | $0.000628 |
| ESCALATED | 8 | $0.000576 |
| NEEDS_APPROVAL | 7 | $0.000787 |
| threat (blocked/quarantined/held) | 9 | $0.000000 |

## The full 9-email night

* **$0.00400** per night (min $0.00383, max $0.00414); 22 model calls, 18,933 input / 5,397 cached / 5,145 output tokens.
* **$0.000444** per email on this mix (3 of 9 are threats that cost $0).
* Email 9 (the auto-sent example): 13 s from webhook to sent reply.

## Scale model (400 supplier emails per user per month, measured cost per email)

| Users | LLM (measured) | Hosting, Fly.io (est.) | AgentMail (list price) | Total / month | Per user |
|---:|---:|---:|---:|---:|---:|
| 1 | $0.18 | $2.00 | $0.00 | $2.18 | $2.18 |
| 100 | $17.78 | $2.00 | $200.00 | $219.78 | $2.20 |
| 10,000 | $1,777.63 | $200.00 | $13,400.00 | $15,377.63 | $1.54 |

Assumptions: hosting is one ~$2/month Fly.io machine per 100 users (Wei's estimate; IMAP polling is light). AgentMail is $0 for up to 3 inboxes (free tier), then the Startup plan ($200/month per 150 inboxes, agentmail.to/pricing) before any enterprise discount. Using Gmail/IMAP instead of AgentMail removes that line.

## Cost-cut experiment: REASONING_EFFORT=low

| | Default effort | Low effort | Change |
|---|---:|---:|---:|
| $ per 9-email night | $0.00400 | $0.00341 | -15% |
| Output tokens per night | 5,145 | 3,991 | -22% |
| Input tokens per night | 18,933 | 18,776 | |
| Expected outcomes matched | 8, 9, 8 of 9 | 8, 9, 8 of 9 | |
| Webhook→sent, email 9 | 13 s | 11 s | |

* Outcome distribution per email: identical at both settings.
* Emails whose outcome varied between runs: email 2 (default ESCALATED ×2, NEEDS_APPROVAL ×1; low ESCALATED ×2, NEEDS_APPROVAL ×1). Live triage is not fully deterministic. Topics are the union of the model's and the regex detector's, so the model can add an escalation but can never remove one the regex found.
* Drafts that differ from the first default run: default reruns 12/12, low effort 18/18. Drafts change wording on every run even at the same setting, so a draft difference alone is not a quality loss; outcomes and compliance results are the quality signal.
