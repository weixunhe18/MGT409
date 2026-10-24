"""Supplier Whisperer: one command to run.

    python app.py                 dashboard at http://127.0.0.1:8000 (opens your browser)
    python app.py --demo          replay the 9 sample emails in the terminal (no browser)
    python app.py --test          run the test suite
    python app.py --help          all options

Standard library only in mock mode. With PORTKEY_API_KEY in .env (this folder or the one above)
the agents run on gpt-6-luna through Portkey.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import unittest
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit("Supplier Whisperer needs Python 3.10 or newer (you have %d.%d)." % sys.version_info[:2])

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(errors="replace")  # Windows consoles + emoji/° symbols
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from supplier_agent.config import AppConfig, load_policy, load_sample_events  # noqa: E402
from supplier_agent.knowledge import KnowledgeBase  # noqa: E402
from supplier_agent.llm import PortkeyLLM  # noqa: E402
from supplier_agent.pipeline import Pipeline  # noqa: E402
from supplier_agent.store import Store  # noqa: E402
from supplier_agent.webhook import dumps, signed_headers, verify  # noqa: E402


def run_demo(config: AppConfig, risk: str, schedule: str, show_drafts: bool) -> int:
    policy = load_policy(config.dataset_dir)
    kb = KnowledgeBase.load(config.dataset_dir / "product_spec.md")
    store = Store(":memory:")
    live = None
    if config.live_available and config.llm_mode != "mock":
        live = PortkeyLLM(config.portkey_api_key, config.portkey_base_url, config.model, config.portkey_provider,
                          config.reasoning_effort, cache=config.portkey_cache)
    pipeline = Pipeline(store=store, kb=kb, policy=policy, config=config, live_llm=live)
    store.set_settings({"risk_tolerance": risk, "schedule_mode": schedule})
    events = load_sample_events(config.dataset_dir)
    engine = f"{config.model} via Portkey (LIVE, real tokens)" if live else "mock engine (offline, estimated tokens)"
    print(f"\nSupplier Whisperer demo · dataset '{config.dataset_dir.name}' · {len(events)} emails · {engine}")
    print(f"risk tolerance = {risk} · schedule = {schedule}\n")
    print(f"{'#':>2}  {'from':<22} {'outcome':<15} {'calls':>5} {'in':>6} {'cached':>6} {'out':>5} {'cost $':>9}  check")
    print("-" * 96)
    mismatches = hits = 0
    totals = {"input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0}
    for i, event in enumerate(events, 1):
        body = dumps(event)
        ok, why = verify(config.webhook_secret, signed_headers(config.webhook_secret, body), body)
        if not ok:
            print(f"{i:>2}  webhook rejected: {why}")
            continue
        run = pipeline.process(json.loads(body.decode("utf-8")), signature_note="Svix signature verified")
        usage = run.get("usage", {})
        hits += sum(c.get("gateway_cache") == "HIT" for c in run.get("calls") or [])
        for key in totals:
            totals[key] += usage.get(key, 0)
        expected = (event.get("_demo") or {}).get("expected")
        check = ""
        if expected and risk == "medium" and schedule == "autonomous":
            check = "ok" if expected == run["outcome"] else f"MISMATCH (expected {expected})"
            mismatches += expected != run["outcome"]
        sender = (run["email"].get("from_name") or run["email"].get("from_addr") or "")[:22]
        print(f"{i:>2}  {sender:<22} {run['outcome']:<15} {usage.get('calls', 0):>5} {usage.get('input_tokens', 0):>6} "
              f"{usage.get('cached_tokens', 0):>6} {usage.get('output_tokens', 0):>5} {usage.get('cost_usd', 0):>9.6f}  {check}")
        print(f"    -> {run.get('headline', '')}")
        if show_drafts and run.get("draft"):
            print("    " + "\n    ".join(run["draft"]["body"].splitlines()))
            print()
    print("-" * 96)
    print(f"Total: {totals['calls']} model calls · {totals['input_tokens']} input / {totals['cached_tokens']} cached / "
          f"{totals['output_tokens']} output tokens · ${totals['cost_usd']:.6f}"
          + ("  (estimated: mock engine)" if not live else ""))
    outbox = store.list_outbox()
    if hits:
        print(f"Note: {hits} call(s) were answered from Portkey's response cache (same answer and token counts as an "
              "earlier identical call). Set PORTKEY_CACHE=refresh for fresh answers.")
    print(f"Mock outbox: {len(outbox)} repl{'y' if len(outbox) == 1 else 'ies'} 'sent' (nothing leaves this computer).")
    if mismatches:
        print(f"\n{mismatches} outcome(s) differ from the expected demo script.")
    return 0


def run_tests() -> int:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Supplier Whisperer: overnight supplier-email agent.")
    parser.add_argument("--demo", action="store_true", help="run the sample inbox in the terminal and exit")
    parser.add_argument("--test", action="store_true", help="run the test suite and exit")
    parser.add_argument("--dataset", default=None, help="dataset folder name under data/ or a path (default: sample)")
    parser.add_argument("--port", type=int, default=None, help="port for the dashboard (default 8000)")
    parser.add_argument("--host", default=None,
                        help="host to bind (default 127.0.0.1). Non-local hosts are refused unless WEBHOOK_SECRET "
                             "and ALLOW_REMOTE=1 are set: the dashboard has no login.")
    parser.add_argument("--fly-private", action="store_true",
                        help="Fly.io only: listen on the machine's private network address (fdaa::/16), reachable "
                             "only through `fly proxy` from your own Fly account. Never a public interface.")
    engine = parser.add_mutually_exclusive_group()
    engine.add_argument("--live", action="store_true", help="force gpt-6-luna via Portkey (needs PORTKEY_API_KEY)")
    engine.add_argument("--mock", action="store_true", help="force the offline mock engine (no key, no cost)")
    parser.add_argument("--risk", choices=("low", "medium", "high"), default="medium", help="--demo risk tolerance")
    parser.add_argument("--schedule", choices=("autonomous", "supervised", "clock"), default="autonomous",
                        help="--demo schedule mode")
    parser.add_argument("--show-drafts", action="store_true", help="--demo: print every drafted reply")
    parser.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    parser.add_argument("--replay", action="store_true", help="reset and replay the sample inbox right after start")
    parser.add_argument("--reset", action="store_true", help="delete this dataset's local database first")
    parser.add_argument("--mailbox", action="store_true",
                        help="connect the real Gmail inbox (IMAP/SMTP). Needs GMAIL_APP_PASSWORD in .env. Replies are "
                             "dry-run unless MAILBOX_SEND=on. Uses its own database, separate from the demo.")
    args = parser.parse_args(argv)

    if args.test:
        return run_tests()

    llm_mode = "live" if args.live else "mock" if args.mock else None
    config = AppConfig.from_env(dataset=args.dataset, host=args.host, port=args.port, llm_mode=llm_mode)
    if args.fly_private:
        if args.host:
            parser.error("--fly-private and --host can't be combined")
        from supplier_agent.server import resolve_fly_private

        config.host, config.fly_private = resolve_fly_private(), True
    if args.live and not config.live_available:
        print("--live needs PORTKEY_API_KEY in .env (this folder or the folder above). Falling back to mock.")
        config.llm_mode = "mock"

    if args.demo:
        return run_demo(config, args.risk, args.schedule, args.show_drafts)

    mailbox_cfg = None
    if args.mailbox:
        from supplier_agent.mailbox import MailboxConfig, check_login

        mailbox_cfg = MailboxConfig.from_env(load_policy(config.dataset_dir))
        check_login(mailbox_cfg)
        if not os.getenv("WHISPERER_DB"):  # real conversations never share the demo's resettable database
            config.db_path = config.db_path.with_name(config.db_path.stem + "-mailbox.db")

    if args.reset and config.db_path.exists():
        config.db_path.unlink()
        print(f"Deleted {config.db_path}")
    from supplier_agent.server import run_server

    run_server(config, open_browser=not args.no_browser, replay=args.replay, mailbox_cfg=mailbox_cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
