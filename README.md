# MGT 409 (AI Foundations for Managers): Wei He

## ➜ Final project: 🌙 Supplier Whisperer

**The app is in [`project1/supplier-whisperer/`](project1/supplier-whisperer/).** An AI agent that works the night
shift with overseas hardware suppliers: it answers from the product spec, asks the supplier for what the engineer
needs, catches statements that contradict the spec, and never commits to price, quantity, dates or orders.

| | |
|---|---|
| Report | [`project1/supplier-whisperer/report.html`](project1/supplier-whisperer/report.html) (download and double-click) |
| Slides | [`project1/supplier-whisperer/slides.html`](project1/supplier-whisperer/slides.html) |
| How to run | [`project1/supplier-whisperer/README.md`](project1/supplier-whisperer/README.md) |
| Demo video | [`project1/supplier-whisperer/docs/demo_video.mp4`](project1/supplier-whisperer/docs/demo_video.mp4) (2.5 min, narrated) |

### Run it (about 2 minutes)

Requires Python 3.10+. From the folder you cloned into:

```bash
cd MGT409/project1/supplier-whisperer
python3 app.py
```

The dashboard opens at http://127.0.0.1:8000. Click **▶ Run demo inbox (13 emails)** and watch the
**Agents at work** panel. With no key it runs on the offline mock engine. For live **gpt-6-luna**:

```bash
pip install -r requirements.txt
python3 app.py --live
```

The app finds `PORTKEY_API_KEY` in a `.env` placed in the app folder, the folder above it, the repo root, **or one
level above the repo** (the course staff layout: `submissions/.env` next to `submissions/MGT409/`). No other key is
needed; see `project1/supplier-whisperer/.env.example`.

Tests: `python3 app.py --test` (114 tests, no network, no key).

---

The other folders are course lectures and homework (`hw1`–`hw6`, `Lectures *`), not part of the final project.
