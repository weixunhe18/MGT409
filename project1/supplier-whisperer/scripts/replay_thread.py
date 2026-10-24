"""Replay a real (anonymized) supplier thread through the pipeline, one supplier email at a time.

    python scripts/replay_thread.py data/raw_private/supplier_01/dataset \
        --thread data/raw_private/supplier_01/anonymized/thread.json --out results_mock.json [--live]

The dataset folder holds product_spec.md, policy.json and emails.json (events from anonymize_chat.py).
Before each supplier email, the buyer's REAL replies up to that moment are put into the thread history,
and the agent's own drafts are removed again afterwards. So every email is judged against the
conversation as it actually happened, not against what the agent would have said earlier.
A simulated clock makes timestamps (and thread-memory ordering) follow the original thread.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from supplier_agent import pipeline as pipeline_mod, store as store_mod  # noqa: E402
from supplier_agent.config import AppConfig, load_policy, load_sample_events  # noqa: E402
from supplier_agent.knowledge import KnowledgeBase  # noqa: E402
from supplier_agent.llm import PortkeyLLM  # noqa: E402
from supplier_agent.pipeline import Pipeline  # noqa: E402
from supplier_agent.store import Store  # noqa: E402


def iso(stamp: str) -> str:
    """'2026-04-29 21:06 -04:00' -> '2026-04-29T21:06:00' (the thread's own local time)."""
    return datetime.strptime(stamp[:16], "%Y-%m-%d %H:%M").isoformat(timespec="seconds")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("dataset", type=Path)
    ap.add_argument("--thread", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--risk", default="medium", choices=("low", "medium", "high"))
    args = ap.parse_args(argv)

    config = AppConfig.from_env(dataset=str(args.dataset), llm_mode="live" if args.live else "mock")
    config.db_path = Path(":memory:")
    live = None
    if args.live:
        if not config.live_available:
            sys.exit("--live needs PORTKEY_API_KEY")
        live = PortkeyLLM(config.portkey_api_key, config.portkey_base_url, config.model, config.portkey_provider,
                          config.reasoning_effort)
    policy = load_policy(config.dataset_dir)
    store = Store(":memory:")
    pipe = Pipeline(store=store, kb=KnowledgeBase.load(config.dataset_dir / "product_spec.md"), policy=policy,
                    config=config, live_llm=live)
    store.set_settings({"risk_tolerance": args.risk, "schedule_mode": "autonomous",
                        "llm_mode": "live" if live else "mock", "daily_budget_usd": 5.0})

    clock = {"now": ""}
    store_mod.now_iso = pipeline_mod.now_iso = lambda: clock["now"]  # simulated clock

    thread = json.loads(args.thread.read_text(encoding="utf-8"))
    buyer = [m for m in thread if m["role"] == "buyer"]
    events = load_sample_events(config.dataset_dir)
    inserted, results = set(), []
    for n, event in enumerate(events, 1):
        msg = event["message"]
        first = min(event["_source_messages"])
        for b in buyer:  # Wei's real replies so far become thread history
            if b["i"] < first and b["i"] not in inserted:
                inserted.add(b["i"])
                clock["now"] = iso(b["at"])
                body = b["text"] or f"[{b['attachment']} attachment]"
                store.add_outbox(0, msg["thread_id"], "rep@supplier.example", "RE: thread", body, "wei")
        clock["now"] = iso(msg["timestamp"])
        run = pipe.process(copy.deepcopy(event), signature_note="replay of a real thread")
        store._write("DELETE FROM outbox WHERE sent_by IN ('agent', 'human')")  # keep history = what really happened
        last = max(event["_source_messages"])
        actual = next((b for b in buyer if b["i"] > last), None)
        results.append({
            "n": n, "at": msg["timestamp"], "messages": event["_source_messages"],
            "supplier_text": msg["text"], "outcome": run.get("outcome"), "headline": run.get("headline"),
            "hard_topics": (run.get("triage") or {}).get("hard_topics", []),
            "engineering_change": (run.get("triage") or {}).get("engineering_change"),
            "sent": bool(run.get("sent")), "draft": (run.get("draft") or {}).get("body", ""),
            "cost_usd": (run.get("usage") or {}).get("cost_usd", 0),
            "tokens": {k: (run.get("usage") or {}).get(k, 0) for k in ("input_tokens", "cached_tokens", "output_tokens")},
            "wei_actual_next": {"at": actual["at"], "text": actual["text"] or f"[{actual['attachment']}]"} if actual else None,
        })
        print(f"{n:>2} {msg['timestamp'][:16]}  {run.get('outcome', '?'):<15} {', '.join(results[-1]['hard_topics']) or '-':<28}"
              f" {msg['text'][:60]!r}")
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    counts: dict[str, int] = {}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    total = sum(r["cost_usd"] for r in results)
    print(f"\n{len(results)} emails · " + " · ".join(f"{k} {v}" for k, v in sorted(counts.items()))
          + f" · ${total:.4f}" + ("" if live else " (estimated: mock)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
