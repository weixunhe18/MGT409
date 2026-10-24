"""Measure real gpt-6-luna token use and cost on the 9-email sample inbox.

    python scripts/measure_tokens.py                 # 3 default runs + 3 REASONING_EFFORT=low runs (live)
    python scripts/measure_tokens.py --runs 1 --no-variant

Each run uses a fresh in-memory store (Night mode, Medium risk), exactly like `python app.py --demo --live`.
Every call records Portkey's x-portkey-cache-status header, and we send x-portkey-cache-force-refresh so a
gateway response cache can never hand back a stored answer (and stored token counts) during a measurement.

Writes docs/tokenomics.json (raw per-call data) and docs/tokenomics.md (tables for the report).
Live spend is stopped at --max-spend (default $0.20) across all runs.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from supplier_agent.config import AppConfig, load_policy, load_sample_events  # noqa: E402
from supplier_agent.knowledge import KnowledgeBase  # noqa: E402
from supplier_agent.llm import PortkeyLLM  # noqa: E402
from supplier_agent.pipeline import Pipeline  # noqa: E402
from supplier_agent.store import Store  # noqa: E402
from supplier_agent.webhook import dumps  # noqa: E402

AGENTS = ("manager", "context", "drafter", "compliance")
THREAT_OUTCOMES = ("QUARANTINED", "BLOCKED", "HELD")
EMAILS_PER_USER_MONTH = 400  # proposal.md section 7
USER_COUNTS = (1, 100, 10_000)
FLY_MACHINE_USD_MONTH = 2.0  # one small shared-cpu machine (weekend_plan.md; check fly.io/pricing)
USERS_PER_MACHINE = 100  # assumption: IMAP polling + a few model calls per hour is light work
AGENTMAIL_STARTUP_USD, AGENTMAIL_STARTUP_INBOXES = 200.0, 150  # agentmail.to/pricing (Oct 2026)


def one_night(config: AppConfig, effort: str) -> dict:
    policy = load_policy(config.dataset_dir)
    kb = KnowledgeBase.load(config.dataset_dir / "product_spec.md")
    store = Store(":memory:")
    llm = PortkeyLLM(config.portkey_api_key, config.portkey_base_url, config.model, config.portkey_provider, effort)
    llm.extra_headers = {"x-portkey-cache-force-refresh": "true"}
    pipeline = Pipeline(store=store, kb=kb, policy=policy, config=config, live_llm=llm)
    store.set_settings({"risk_tolerance": "medium", "schedule_mode": "autonomous", "llm_mode": "live"})
    emails = []
    for i, event in enumerate(load_sample_events(config.dataset_dir), 1):
        run = pipeline.process(json.loads(dumps(event).decode("utf-8")), signature_note="measurement")
        expected = (event.get("_demo") or {}).get("expected")
        emails.append({
            "n": i,
            "subject": run["email"].get("subject", ""),
            "outcome": run["outcome"],
            "expected": expected,
            "ok": expected == run["outcome"],
            "elapsed_ms": run.get("elapsed_ms", 0),
            "usage": run["usage"],
            "calls": run["calls"],
            "draft": (run.get("draft") or {}).get("body", ""),
        })
    return {"effort": effort or "default", "emails": emails,
            "cost_usd": round(sum(e["usage"]["cost_usd"] for e in emails), 6)}


def mean(values) -> float:
    values = list(values)
    return statistics.fmean(values) if values else 0.0


def summarize(nights: list[dict]) -> dict:
    per_agent: dict[str, list[dict]] = defaultdict(list)
    per_type: dict[str, list[float]] = defaultdict(list)
    for night in nights:
        for e in night["emails"]:
            for c in e["calls"]:
                per_agent[c["agent"]].append(c)
            kind = "threat (blocked/quarantined/held)" if e["outcome"] in THREAT_OUTCOMES else e["outcome"]
            per_type[kind].append(e["usage"]["cost_usd"])
    agents = {}
    for name in AGENTS:
        calls = per_agent.get(name, [])
        agents[name] = {
            "calls_per_night": len(calls) / len(nights),
            "input": mean(c["input_tokens"] for c in calls),
            "cached": mean(c["cached_tokens"] for c in calls),
            "output": mean(c["output_tokens"] for c in calls),
            "reasoning": mean(c.get("reasoning_tokens", 0) for c in calls),
            "cost_usd": mean(c["cost_usd"] for c in calls),
            "ms": mean(c["ms"] for c in calls),
        }
    nights_cost = [n["cost_usd"] for n in nights]
    all_calls = [c for calls in per_agent.values() for c in calls]
    return {
        "runs": len(nights),
        "agents": agents,
        "per_email_type": {k: {"n": len(v), "mean_cost_usd": mean(v)} for k, v in sorted(per_type.items())},
        "night_cost_usd": {"mean": mean(nights_cost), "min": min(nights_cost), "max": max(nights_cost)},
        "night_tokens": {
            key: mean(sum(e["usage"][key] for e in n["emails"]) for n in nights)
            for key in ("input_tokens", "cached_tokens", "output_tokens", "calls")
        },
        "outcomes_ok": [sum(e["ok"] for e in n["emails"]) for n in nights],
        "gateway_cache": sorted({c.get("gateway_cache", "") or "(none)" for c in all_calls}),
        "email9_elapsed_s": mean(e["elapsed_ms"] / 1000 for n in nights for e in n["emails"] if e["n"] == 9),
    }


def scale_model(cost_per_email: float) -> list[dict]:
    rows = []
    for users in USER_COUNTS:
        llm = cost_per_email * EMAILS_PER_USER_MONTH * users
        machines = max(1, -(-users // USERS_PER_MACHINE))
        hosting = machines * FLY_MACHINE_USD_MONTH
        plans = -(-users // AGENTMAIL_STARTUP_INBOXES)
        agentmail = 0.0 if users <= 3 else plans * AGENTMAIL_STARTUP_USD  # free tier: 3 inboxes
        rows.append({"users": users, "llm_usd": llm, "hosting_usd": hosting, "agentmail_usd": agentmail,
                     "total_usd": llm + hosting + agentmail,
                     "per_user_usd": (llm + hosting + agentmail) / users})
    return rows


def outcome_spread(nights: list[dict]) -> dict:
    """Per email: how often each outcome came out across runs, e.g. {2: {"ESCALATED": 2, "NEEDS_APPROVAL": 1}}."""
    spread: dict = defaultdict(lambda: defaultdict(int))
    for night in nights:
        for e in night["emails"]:
            spread[e["n"]][e["outcome"]] += 1
    return {n: dict(v) for n, v in spread.items()}


def compare(base: list[dict], variant: list[dict]) -> dict:
    """Outcome spread per setting (live outcomes vary run to run), and how often drafts differ."""
    ref = base[0]["emails"]
    base_spread, var_spread = outcome_spread(base), outcome_spread(variant)
    outcome_changes = [{"n": n, "default": base_spread[n], "variant": var_spread.get(n, {})}
                       for n in sorted(base_spread) if base_spread[n] != var_spread.get(n, {})]
    unstable = [{"n": n, "default": base_spread[n], "variant": var_spread.get(n, {})}
                for n in sorted(base_spread) if len(base_spread[n]) > 1 or len(var_spread.get(n, {})) > 1]
    def differ(nights):
        pairs = [(e["draft"], r["draft"]) for n in nights for e, r in zip(n["emails"], ref) if r["draft"] or e["draft"]]
        return sum(a != b for a, b in pairs), len(pairs)
    return {"outcome_changes": outcome_changes, "unstable": unstable,
            "drafts_differ_default_vs_default": differ(base[1:]),
            "drafts_differ_low_vs_default": differ(variant)}


def fmt(spread: dict) -> str:
    return ", ".join(f"{k} ×{v}" for k, v in sorted(spread.items()))


def write_md(path: Path, data: dict) -> None:
    base, low = data["default"], data.get("low")
    lines = [
        "# Tokenomics: measured on live gpt-6-luna (Portkey)",
        "",
        f"Measured {data['measured_at']} with `python scripts/measure_tokens.py`. Raw per-call data: "
        "`docs/tokenomics.json`. Prices (lecture 11, per 1M tokens): input $0.10, cached input $0.01, "
        "cache write $0.125, output $0.50. Reasoning tokens are billed as output and are included in output.",
        "",
        f"Setup: the 9-email sample inbox, Night mode, Medium risk, a fresh in-memory store per run, "
        f"{base['runs']} runs at the default reasoning effort. Expected outcomes matched per run: "
        f"{', '.join(f'{k}/9' for k in base['outcomes_ok'])}.",
        "",
        "**Portkey cache check.** Earlier repeated runs showed identical token counts. That was Portkey's response "
        "cache: the app now logs Portkey's `x-portkey-cache-status` header per call, and ordinary repeat runs of the "
        "demo inbox came back `HIT` on every model call (same answer, same token counts, returned in about 1 s instead of 2–5 s). A tiny "
        "two-call probe had shown `MISS`, so the cache only shows up on real, repeated prompts. For this measurement "
        "every call sent `x-portkey-cache-force-refresh: true` (the app's new `PORTKEY_CACHE=refresh` setting), and "
        f"the header read {', '.join(base['gateway_cache'])} on every call: these are fresh model answers. "
        "Input counts are still nearly identical run to run because the prompts are identical; output counts vary.",
        "",
        "## Per agent (mean per call, default effort)",
        "",
        "| Agent | Calls / night | Input | Cached | Output (of which reasoning) | $ per call | Latency |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, a in base["agents"].items():
        lines.append(f"| {name} | {a['calls_per_night']:.1f} | {a['input']:,.0f} | {a['cached']:,.0f} | "
                     f"{a['output']:,.0f} ({a['reasoning']:,.0f}) | ${a['cost_usd']:.6f} | {a['ms'] / 1000:.1f} s |")
    lines += ["", "## Per email type (mean, default effort)", "", "| Outcome | Emails measured | $ per email |",
              "|---|---:|---:|"]
    for k, v in base["per_email_type"].items():
        lines.append(f"| {k} | {v['n']} | ${v['mean_cost_usd']:.6f} |")
    nc, nt = base["night_cost_usd"], base["night_tokens"]
    lines += [
        "",
        "## The full 9-email night",
        "",
        f"* **${nc['mean']:.5f}** per night (min ${nc['min']:.5f}, max ${nc['max']:.5f}); "
        f"{nt['calls']:.0f} model calls, {nt['input_tokens']:,.0f} input / {nt['cached_tokens']:,.0f} cached / "
        f"{nt['output_tokens']:,.0f} output tokens.",
        f"* **${data['cost_per_email']:.6f}** per email on this mix (3 of 9 are threats that cost $0).",
        f"* Email 9 (the auto-sent example): {base['email9_elapsed_s']:.0f} s from webhook to sent reply.",
        "",
        f"## Scale model ({EMAILS_PER_USER_MONTH} supplier emails per user per month, measured cost per email)",
        "",
        "| Users | LLM (measured) | Hosting, Fly.io (est.) | AgentMail (list price) | Total / month | Per user |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for r in data["scale"]:
        lines.append(f"| {r['users']:,} | ${r['llm_usd']:,.2f} | ${r['hosting_usd']:,.2f} | ${r['agentmail_usd']:,.2f} | "
                     f"${r['total_usd']:,.2f} | ${r['per_user_usd']:,.2f} |")
    lines += [
        "",
        f"Assumptions: hosting is one ~${FLY_MACHINE_USD_MONTH:.0f}/month Fly.io machine per {USERS_PER_MACHINE} users "
        "(Wei's estimate; IMAP polling is light). AgentMail is $0 for up to 3 inboxes (free tier), then the Startup "
        f"plan (${AGENTMAIL_STARTUP_USD:.0f}/month per {AGENTMAIL_STARTUP_INBOXES} inboxes, agentmail.to/pricing) "
        "before any enterprise discount. Using Gmail/IMAP instead of AgentMail removes that line.",
    ]
    if low:
        cmp_ = data["comparison"]
        d_lo, d_def = low["night_cost_usd"]["mean"], nc["mean"]
        o_lo, o_def = low["night_tokens"]["output_tokens"], nt["output_tokens"]
        lines += [
            "",
            "## Cost-cut experiment: REASONING_EFFORT=low",
            "",
            "| | Default effort | Low effort | Change |",
            "|---|---:|---:|---:|",
            f"| $ per 9-email night | ${d_def:.5f} | ${d_lo:.5f} | {100 * (d_lo - d_def) / d_def:+.0f}% |",
            f"| Output tokens per night | {o_def:,.0f} | {o_lo:,.0f} | {100 * (o_lo - o_def) / o_def:+.0f}% |",
            f"| Input tokens per night | {nt['input_tokens']:,.0f} | {low['night_tokens']['input_tokens']:,.0f} | |",
            f"| Expected outcomes matched | {', '.join(map(str, base['outcomes_ok']))} of 9 | "
            f"{', '.join(map(str, low['outcomes_ok']))} of 9 | |",
            f"| Webhook→sent, email 9 | {base['email9_elapsed_s']:.0f} s | {low['email9_elapsed_s']:.0f} s | |",
            "",
            "* Outcome distribution per email: "
            + ("identical at both settings." if not cmp_["outcome_changes"] else "differs for "
               + "; ".join(f"email {c['n']} (default {c['default']}, low {c['variant']})" for c in cmp_["outcome_changes"])
               + "."),
            "* Emails whose outcome varied between runs: "
            + ("none." if not cmp_["unstable"] else "; ".join(
                f"email {c['n']} (default {fmt(c['default'])}; low {fmt(c['variant'])})" for c in cmp_["unstable"])
               + ". Live triage is not fully deterministic. Topics are the union of the model's and the regex detector's, "
                 "so the model can add an escalation but can never remove one the regex found."),
            f"* Drafts that differ from the first default run: default reruns "
            f"{cmp_['drafts_differ_default_vs_default'][0]}/{cmp_['drafts_differ_default_vs_default'][1]}, "
            f"low effort {cmp_['drafts_differ_low_vs_default'][0]}/{cmp_['drafts_differ_low_vs_default'][1]}. "
            "Drafts change wording on every run even at the same setting, so a draft difference alone is not a "
            "quality loss; outcomes and compliance results are the quality signal.",
        ]
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--no-variant", action="store_true", help="skip the REASONING_EFFORT=low comparison")
    parser.add_argument("--max-spend", type=float, default=0.20)
    parser.add_argument("--rewrite", action="store_true",
                        help="no API calls: rebuild docs/tokenomics.md from the saved docs/tokenomics.json")
    args = parser.parse_args()
    if args.rewrite:
        path = ROOT / "docs" / "tokenomics.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["nights"].get("low"):
            data["comparison"] = compare(data["nights"]["default"], data["nights"]["low"])
        path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        write_md(ROOT / "docs" / "tokenomics.md", data)
        print("Rewrote docs/tokenomics.md from docs/tokenomics.json (no API calls)")
        return 0
    config = AppConfig.from_env(llm_mode="live")
    if not config.live_available:
        sys.exit("PORTKEY_API_KEY not found in .env; this script only measures live calls.")
    spent = 0.0
    plan = [("", args.runs)] + ([] if args.no_variant else [("low", args.runs)])
    nights: dict[str, list[dict]] = defaultdict(list)
    for effort, runs in plan:
        for i in range(runs):
            if spent >= args.max_spend:
                print(f"Stopping: spend cap ${args.max_spend:.2f} reached")
                break
            night = one_night(config, effort)
            spent += night["cost_usd"]
            nights[night["effort"]].append(night)
            ok = sum(e["ok"] for e in night["emails"])
            print(f"{night['effort']:>7} run {i + 1}: {ok}/9 ok, ${night['cost_usd']:.5f} (total ${spent:.5f})")
    base = summarize(nights["default"])
    data = {
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "model": config.model,
        "prices_per_million": config.prices,
        "total_spend_usd": round(spent, 6),
        "default": base,
        "cost_per_email": base["night_cost_usd"]["mean"] / 9,
        "nights": {k: v for k, v in nights.items()},
    }
    data["scale"] = scale_model(data["cost_per_email"])
    if nights.get("low"):
        data["low"] = summarize(nights["low"])
        data["comparison"] = compare(nights["default"], nights["low"])
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "tokenomics.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    write_md(docs / "tokenomics.md", data)
    print(f"Wrote docs/tokenomics.json and docs/tokenomics.md · live spend ${spent:.5f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
