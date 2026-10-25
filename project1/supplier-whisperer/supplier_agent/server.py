"""Local web server (standard library): dashboard, JSON API, and the AgentMail-style webhook.

POST /webhook/agentmail   signed `message.received` events (Svix scheme), the ONLY trigger for the agents
GET  /                    dashboard
GET  /api/state           everything the dashboard polls
GET  /api/runs/<id>       one email: trace, draft, compliance, tokens
POST /api/...             human-in-the-loop actions (require header X-Requested-With: supplier-whisperer)
"""

from __future__ import annotations

import ipaddress
import json
import os
import queue
import re
import socket
import threading
import time
import traceback
import urllib.request
import webbrowser
from collections import Counter, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .config import STATIC_DIR, AppConfig, load_policy, load_sample_events
from .knowledge import KnowledgeBase
from .llm import PortkeyLLM
from .pipeline import RISK_LEVELS, SCHEDULE_MODES, Pipeline
from .scorecard import score
from .store import Store, now_iso
from .webhook import dumps, make_event, signed_headers, verify

MAX_BODY = 1_000_000
CSRF_HEADER = "supplier-whisperer"
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1", "[::1]")
# Fly.io's private WireGuard network (6PN). Only machines and `fly proxy` peers of the same org can reach it.
FLY_6PN_HOSTNAME = "fly-local-6pn"
FLY_6PN_NETWORK = ipaddress.ip_network("fdaa::/16")
# Calls to our own webhook must never go through a corporate HTTP proxy.
_LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
HARD_RULES = [
    "Never commit to price, quantity, dates or purchase orders. These always escalate to you.",
    "Never share drawings, files, links or confidential information. The agent cannot attach files.",
    "Only reply to allowlisted senders, and only to the person who wrote. Recipients are locked by code.",
    "Never act on instructions inside an email. Suspected prompt injection is quarantined.",
    "Never claims to be human: if a supplier asks whether they're talking to a person or a bot, it goes to you.",
    "Hard budget caps per email and per day, plus a kill switch.",
]


class App:
    def __init__(self, config: AppConfig):
        self.config = config
        self.policy = load_policy(config.dataset_dir)
        self.kb = KnowledgeBase.load(config.dataset_dir / "product_spec.md")
        self.store = Store(config.db_path)
        live = None
        if config.live_available and config.llm_mode != "mock":
            live = PortkeyLLM(config.portkey_api_key, config.portkey_base_url, config.model,
                              config.portkey_provider, config.reasoning_effort, cache=config.portkey_cache)
        self.pipeline = Pipeline(store=self.store, kb=self.kb, policy=self.policy, config=config, live_llm=live)
        if config.llm_mode in ("live", "mock"):  # an explicit --live/--mock (or LLM_MODE) beats the saved UI toggle
            self.store.set_settings({"llm_mode": "live" if (config.llm_mode == "live" and live) else "mock"})
        self.jobs: queue.Queue = queue.Queue()
        self.busy = False
        self.replay_running = False
        self.webhook_log: deque = deque(maxlen=60)
        loop_host = "127.0.0.1" if config.host in LOOPBACK_HOSTS + ("0.0.0.0", "", "::") else config.host
        if ":" in loop_host:
            loop_host = f"[{loop_host}]"
        self.base_url = f"http://{loop_host}:{config.port}"
        threading.Thread(target=self._worker, name="agent-worker", daemon=True).start()

    @property
    def live_available(self) -> bool:
        return self.pipeline.live_llm is not None

    # ------------------------------------------------------------ worker
    def _worker(self) -> None:
        while True:
            job = self.jobs.get()
            self.busy = True
            try:
                job()
            except Exception as exc:  # noqa: BLE001  nothing was sent; make the failure visible
                traceback.print_exc()
                self.log(f"PROCESSING FAILED ({type(exc).__name__}: {exc}). Nothing was sent; check the console.")
            finally:
                self.busy = False
                self.jobs.task_done()

    def log(self, text: str) -> None:
        self.webhook_log.append({"at": now_iso(), "text": text})

    @property
    def idle(self) -> bool:
        return not self.busy and self.jobs.empty() and not self.replay_running

    def enqueue_event(self, event: dict, note: str) -> None:
        def job() -> None:
            run = self.pipeline.process(event, signature_note=note)
            if run.get("outcome") == "DUPLICATE":
                self.log(f"duplicate ignored: {run.get('message_id')} (already processed)")

        self.jobs.put(job)

    def post_signed(self, event: dict) -> int:
        """Deliver an event to our own webhook exactly like AgentMail would (signed HTTP POST)."""
        body = dumps(event)
        request = urllib.request.Request(self.base_url + "/webhook/agentmail", data=body, method="POST",
                                         headers=signed_headers(self.config.webhook_secret, body))
        with _LOCAL_OPENER.open(request, timeout=15) as response:
            return int(response.status)

    def start_mailbox(self, mailbox) -> None:
        """Poll the real inbox; process mail on the agent worker, then deliver replies on the same worker."""
        self.mailbox = mailbox
        self.pipeline.mailbox_allow = list(mailbox.cfg.extra_allow)

        def deliver() -> None:
            mailbox.deliver_pending()
            mailbox.send_digests()  # approve-by-email (only when MY_PERSONAL_EMAIL is a separate address)

        def loop() -> None:
            while True:
                try:
                    events = mailbox.fetch_new()
                    if events:
                        self.log(f"Gmail: {len(events)} new message(s)")
                    for event in events:
                        msg = event["message"]
                        auth = "DKIM/DMARC pass" if msg["auth"]["verified"] else "DKIM/DMARC FAILED"
                        self.log(f"Gmail: new mail from {msg['from']} ({auth})")
                        self.enqueue_event(event, f"received via Gmail IMAP · {auth}")
                    for command in mailbox.take_commands():  # APPROVE/EDIT from Wei's own, authenticated address
                        self.jobs.put(lambda c=command: mailbox.handle_command(c, self.pipeline))
                    self.jobs.put(deliver)  # also picks up replies Wei approved in the dashboard
                except Exception as exc:  # noqa: BLE001  keep polling; the next round retries
                    self.log(f"Gmail poll failed ({type(exc).__name__}: {exc}). Retrying next round.")
                time.sleep(mailbox.cfg.poll_seconds)

        threading.Thread(target=loop, name="gmail-poller", daemon=True).start()

    def replay_samples(self, reset: bool) -> bool:
        if not self.idle or getattr(self, "mailbox", None):
            return False  # never wipe a live mailbox's conversations with the demo inbox
        if reset:
            self.store.reset()
        events = load_sample_events(self.config.dataset_dir)
        self.replay_running = True

        def run() -> None:
            try:
                for event in events:
                    try:
                        self.post_signed(event)
                    except Exception as exc:  # noqa: BLE001
                        self.log(f"replay failed for {event.get('event_id')}: {exc}")
                    time.sleep(0.4)
            finally:
                self.replay_running = False

        threading.Thread(target=run, name="replay", daemon=True).start()
        return True

    # ------------------------------------------------------------- state
    def supplier_scores(self) -> list[dict]:
        contacts = {c.get("address"): c for c in self.policy.get("allowlist", []) if isinstance(c, dict)}
        rows = []
        for address, messages in self.store.supplier_conversations().items():
            contact = contacts.get(address) or {}
            rows.append({"address": address, "name": contact.get("name", ""), "company": contact.get("company", ""),
                         **score(messages)})
        return sorted(rows, key=lambda r: -r["overall"])

    def state(self) -> dict:
        s = self.pipeline.settings()
        autonomous, label = self.pipeline.schedule_state(s)
        runs = self.store.list_runs()
        allow = list(self.policy.get("allowlist", [])) + [
            {"address": a, "name": "", "company": "added by you", "role": ""} for a in s.get("extra_allow", [])]
        return {
            "app": {
                "dataset": self.config.dataset_dir.name,
                "model": self.config.model,
                "live_available": self.live_available,
                "autonomous": autonomous,
                "schedule_label": label,
                "now": now_iso(),
                "queue": self.jobs.qsize() + (1 if self.busy else 0),
                "replay_running": self.replay_running,
                "dev_secret": self.config.using_dev_secret,
                "owner": self.policy.get("owner", {}),
                "product": self.policy.get("product_name", ""),
                "samples": len(load_sample_events(self.config.dataset_dir)),
            },
            "settings": {k: s.get(k) for k in ("risk_tolerance", "schedule_mode", "llm_mode", "daily_budget_usd",
                                               "paused")},
            "stats": {"total": len(runs), "by_outcome": dict(Counter(r["outcome"] for r in runs)),
                      "pending": sum(1 for r in runs if r["human_status"] == "pending")},
            "spend": {**self.store.spend_today(), "daily_budget_usd": s["daily_budget_usd"],
                      "prices": self.config.prices},
            "runs": runs,
            "outbox": self.store.list_outbox(60),
            "suppliers": self.supplier_scores(),
            "policy": {"allowlist": allow,
                       "blocklist": list(self.policy.get("blocklist", [])) + list(s.get("extra_block", [])),
                       "hard_rules": HARD_RULES, "limits": self.policy.get("limits", {})},
            "webhook_log": list(self.webhook_log)[-25:],
        }

    def update_settings(self, data: dict) -> tuple[bool, str]:
        values: dict = {}
        if "risk_tolerance" in data:
            if data["risk_tolerance"] not in RISK_LEVELS:
                return False, "risk_tolerance must be low, medium or high"
            values["risk_tolerance"] = data["risk_tolerance"]
        if "schedule_mode" in data:
            if data["schedule_mode"] not in SCHEDULE_MODES:
                return False, "schedule_mode must be clock, autonomous or supervised"
            values["schedule_mode"] = data["schedule_mode"]
        if "llm_mode" in data:
            if data["llm_mode"] not in ("live", "mock"):
                return False, "llm_mode must be live or mock"
            if data["llm_mode"] == "live" and not self.live_available:
                return False, ("Live mode needs PORTKEY_API_KEY in .env (this folder or the one above), "
                               "and the app must not be started with --mock.")
            values["llm_mode"] = data["llm_mode"]
        if "daily_budget_usd" in data:
            try:
                budget = float(data["daily_budget_usd"])
            except (TypeError, ValueError):
                return False, "daily_budget_usd must be a number"
            if not 0 <= budget <= 100:
                return False, "daily_budget_usd must be between 0 and 100"
            values["daily_budget_usd"] = budget
        if "paused" in data:
            values["paused"] = bool(data["paused"])
        self.store.set_settings(values)
        return True, "saved"


class Handler(BaseHTTPRequestHandler):
    server_version = "SupplierWhisperer/0.1"

    @property
    def app(self) -> App:
        return self.server.app  # type: ignore[attr-defined]

    def log_message(self, fmt, *args):  # keep the console readable
        return

    def _host_ok(self) -> bool:
        """When bound to loopback (or Fly's private network, reached through `fly proxy` on localhost), only accept
        Host: localhost/127.0.0.1 (blocks DNS-rebinding attacks)."""
        if self.app.config.host not in LOOPBACK_HOSTS and not self.app.config.fly_private:
            return True
        host = (self.headers.get("Host") or "").strip().lower()
        if host.startswith("["):
            name = host.split("]", 1)[0] + "]"
        else:
            name = host.rsplit(":", 1)[0]
        return name in LOOPBACK_HOSTS or name == ""

    # ------------------------------------------------------------ helpers
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status: int = 200) -> None:
        self._send(status, json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _read_body(self) -> bytes | None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY:
            self._json({"error": "payload too large"}, 413)
            return None
        return self.rfile.read(length) if length > 0 else b""

    def _read_json(self) -> dict | None:
        raw = self._read_body()
        if raw is None:
            return None
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json({"error": "invalid JSON"}, 400)
            return None
        if not isinstance(data, dict):
            self._json({"error": "expected a JSON object"}, 400)
            return None
        return data

    # --------------------------------------------------------------- GET
    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if not self._host_ok():
            return self._json({"error": "bad Host header"}, 403)
        if path in ("/", "/index.html"):
            page = (STATIC_DIR / "index.html").read_bytes()
            return self._send(200, page, "text/html; charset=utf-8")
        if path == "/api/health":
            return self._json({"ok": True, "time": now_iso()})
        if path == "/api/state":
            return self._json(self.app.state())
        m = re.match(r"^/api/runs/(\d+)$", path)
        if m:
            run = self.app.store.get_run(int(m.group(1)))
            if not run:
                return self._json({"error": "not found"}, 404)
            run["feedback"] = self.app.store.feedback_for(run["id"])
            return self._json(run)
        return self._json({"error": "not found"}, 404)

    # -------------------------------------------------------------- POST
    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        if not self._host_ok():
            return self._json({"error": "bad Host header"}, 403)
        if path == "/webhook/agentmail":
            return self._webhook()
        if not path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        if self.headers.get("X-Requested-With") != CSRF_HEADER:
            return self._json({"error": "missing X-Requested-With header"}, 403)
        data = self._read_json()
        if data is None:
            return None
        app = self.app

        if path == "/api/settings":
            ok, msg = app.update_settings(data)
            return self._json({"ok": ok, "message": msg}, 200 if ok else 400)
        if path == "/api/replay":
            started = app.replay_samples(reset=bool(data.get("reset", True)))
            return self._json({"ok": started, "message": "replaying sample inbox" if started
                               else "The agent is still working. Try again in a few seconds."})
        if path == "/api/reset":
            if not app.idle:
                return self._json({"ok": False, "message": "The agent is still working. Try again in a few seconds."})
            app.store.reset()
            return self._json({"ok": True})
        if path == "/api/compose":
            return self._compose(data)
        if path == "/api/senders":
            result = app.pipeline.update_sender_lists(str(data.get("address", "")), str(data.get("action", "")))
            return self._json(result, 200 if result.get("ok") else 400)
        m = re.match(r"^/api/runs/(\d+)/(approve|reject|resolve|feedback|reprocess)$", path)
        if m:
            run_id, action = int(m.group(1)), m.group(2)
            if action == "approve":
                body = data.get("body")
                result = app.pipeline.approve(run_id, body if isinstance(body, str) else None,
                                              force=bool(data.get("force")))
            elif action == "reject":
                result = app.pipeline.set_human_status(run_id, "rejected")
            elif action == "resolve":
                result = app.pipeline.set_human_status(run_id, "resolved")
            elif action == "feedback":
                rating = "up" if data.get("rating") == "up" else "down"
                app.store.add_feedback(run_id, rating, str(data.get("note", ""))[:1000])
                result = {"ok": True}
            else:
                override = bool(data.get("override_injection"))

                def rerun() -> None:
                    outcome = app.pipeline.reprocess(run_id, override_injection=override)
                    if not outcome.get("ok"):
                        app.log(f"re-run of #{run_id} refused: {outcome.get('error')}")

                app.jobs.put(rerun)
                result = {"ok": True, "message": "re-run queued"}
            return self._json(result, 200 if result.get("ok") or result.get("needs_force") else 400)
        return self._json({"error": "not found"}, 404)

    def _webhook(self):
        raw = self._read_body()
        if raw is None:
            return None
        ok, reason = verify(self.app.config.webhook_secret, self.headers, raw)
        if not ok:
            self.app.log(f"REJECTED webhook: {reason}")
            return self._json({"error": reason}, 401)
        try:
            event = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._json({"error": "invalid JSON"}, 400)
        if not isinstance(event, dict) or event.get("event_type") != "message.received":
            return self._json({"status": "ignored", "reason": "unsupported event_type"})
        sender = str((event.get("message") or {}).get("from") or "?")
        self.app.log(f"accepted {event.get('event_id', '')} from {sender} (signature verified)")
        self.app.enqueue_event(event, "Svix signature verified")
        return self._json({"status": "queued"})

    def _compose(self, data: dict):
        from_header = str(data.get("from") or "").strip()
        text = str(data.get("text") or "")
        if "@" not in from_header or not text.strip():
            return self._json({"ok": False, "error": "Need a From address and a body."}, 400)
        event = make_event(from_header=from_header, subject=str(data.get("subject") or "(no subject)")[:300],
                           text=text[:20000], html=(str(data.get("html")) if data.get("html") else None),
                           thread_id=str(data.get("thread_id") or "") or None,
                           inbox_id=str(self.app.policy.get("owner", {}).get("inbox", "")))

        def deliver() -> None:
            try:
                self.app.post_signed(event)
            except Exception as exc:  # noqa: BLE001
                self.app.log(f"compose delivery failed: {exc}")

        threading.Thread(target=deliver, daemon=True).start()
        return self._json({"ok": True, "message_id": event["message"]["message_id"]})


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR lets a second instance silently share the port; only use it elsewhere.
    allow_reuse_address = os.name != "nt"


class _Server6(_Server):
    address_family = socket.AF_INET6


def resolve_fly_private(resolver=socket.getaddrinfo) -> str:
    """The machine's Fly.io private (6PN) address, for `--fly-private`.

    Refuses anything outside fdaa::/16, so this flag can never bind a public interface: on a laptop, or on a
    host where the name resolves elsewhere, the app stops instead of listening."""
    try:
        infos = resolver(FLY_6PN_HOSTNAME, None, socket.AF_INET6)
    except (OSError, UnicodeError):
        infos = []
    for info in infos:
        address = str(info[4][0]).split("%", 1)[0]
        try:
            if ipaddress.ip_address(address) in FLY_6PN_NETWORK:
                return address
        except ValueError:
            continue
    raise SystemExit(f"--fly-private: '{FLY_6PN_HOSTNAME}' does not resolve to a Fly.io private address (fdaa::/16). "
                     "This flag only works inside a Fly.io machine; locally, run without it.")


def run_server(config: AppConfig, open_browser: bool = True, replay: bool = False, mailbox_cfg=None) -> None:
    if config.fly_private:
        if ipaddress.ip_address(config.host) not in FLY_6PN_NETWORK:
            raise SystemExit(f"Refusing to listen on {config.host}: --fly-private only binds fdaa::/16 addresses.")
    elif config.host not in LOOPBACK_HOSTS and (config.using_dev_secret or os.getenv("ALLOW_REMOTE") != "1"):
        raise SystemExit(
            f"Refusing to listen on {config.host}: the dashboard API has no login, so it must stay on 127.0.0.1.\n"
            "To expose the webhook anyway (e.g. for hosting), set a real WEBHOOK_SECRET and ALLOW_REMOTE=1, and put the "
            "app behind an authenticating proxy.")
    app = App(config)
    try:
        httpd = (_Server6 if ":" in config.host else _Server)((config.host, config.port), Handler)
    except OSError as exc:
        raise SystemExit(f"Could not start on port {config.port} ({exc}). Try: python app.py --port {config.port + 1}")
    httpd.app = app  # type: ignore[attr-defined]
    port = httpd.server_address[1]
    app.base_url = app.base_url.rsplit(":", 1)[0] + f":{port}"
    url = f"http://127.0.0.1:{port}" if config.host in LOOPBACK_HOSTS else app.base_url
    if config.fly_private:
        print(f"\n  Private network only ({config.host}). From your laptop: fly proxy {port}, then open "
              f"http://127.0.0.1:{port}")
    mode = (f"LIVE ({config.model} via Portkey)" if app.pipeline.settings()["llm_mode"] == "live"
            else "MOCK (offline; add PORTKEY_API_KEY to .env for gpt-6-luna)")
    print("\n  Supplier Whisperer is running")
    print(f"  Dashboard:  {url}")
    print(f"  Webhook:    POST {url}/webhook/agentmail  (Svix-signed)")
    print(f"  Dataset:    {config.dataset_dir.name}   Model: {mode}")
    print(f"  .env found: {', '.join(str(p) for p in config.env_files) or 'none (mock mode works without it)'}")
    if mailbox_cfg is not None:
        from .mailbox import GmailMailbox

        sending = "SENDING real replies" if mailbox_cfg.sending else "DRY-RUN (replies are NOT sent; MAILBOX_SEND=on)"
        print(f"  Mailbox:    {mailbox_cfg.display_name} <{mailbox_cfg.address}> · every {mailbox_cfg.poll_seconds} s"
              f" · {sending}")
        print(f"  Also allowed (DKIM/DMARC required): {', '.join(mailbox_cfg.extra_allow) or 'none'}")
        print("  Approve by email: " + (f"digests to {mailbox_cfg.owner_email}" if mailbox_cfg.approve_by_email else
                                         "off (MY_PERSONAL_EMAIL unset or the agent's own address)"))
        app.start_mailbox(GmailMailbox(mailbox_cfg, app.store, log=lambda t: (print("  " + t), app.log(t))))
    print("  Press Ctrl+C to stop.\n")
    if replay and mailbox_cfg is None:
        threading.Timer(0.5, lambda: app.replay_samples(reset=True)).start()
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
