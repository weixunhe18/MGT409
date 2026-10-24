"""Act like AgentMail: POST signed `message.received` events to a running Supplier Whisperer.

    python scripts/send_test_webhook.py                      # all sample emails
    python scripts/send_test_webhook.py --only evt_sample_04 # one email
    python scripts/send_test_webhook.py --unsigned           # prove unsigned webhooks get a 401
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from supplier_agent.config import AppConfig, load_sample_events  # noqa: E402
from supplier_agent.webhook import dumps, signed_headers  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=None, help="default http://127.0.0.1:<PORT>/webhook/agentmail")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--only", default=None, help="event_id to send")
    parser.add_argument("--unsigned", action="store_true", help="send without a signature (should be rejected)")
    args = parser.parse_args()

    config = AppConfig.from_env(dataset=args.dataset)
    url = args.url or f"http://127.0.0.1:{config.port}/webhook/agentmail"
    events = [e for e in load_sample_events(config.dataset_dir) if not args.only or e.get("event_id") == args.only]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never route localhost via a proxy
    for event in events:
        body = dumps(event)
        headers = {"Content-Type": "application/json"} if args.unsigned else signed_headers(config.webhook_secret, body)
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with opener.open(request, timeout=10) as response:
                print(f"{event.get('event_id')}: HTTP {response.status} {response.read().decode('utf-8')}")
        except urllib.error.HTTPError as exc:
            print(f"{event.get('event_id')}: HTTP {exc.code} {exc.read().decode('utf-8')}")
        except urllib.error.URLError as exc:
            print(f"Could not reach {url}: {exc.reason}. Is `python app.py` running?")
            return 1
        time.sleep(0.3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
