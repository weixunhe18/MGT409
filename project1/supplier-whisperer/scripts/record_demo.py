"""Record the 2–3 minute demo video: the real dashboard, driven by a script, with narration and captions.

    # one-time, in any venv (NOT needed to run the app):
    pip install playwright imageio-ffmpeg
    # with the dashboard running (python app.py --no-browser) and Google Chrome installed:
    python scripts/record_demo.py --out docs/demo_video.mp4

It resets the demo, clicks "Run demo inbox" (live on gpt-6-luna if a key is configured), narrates what the agents
do while the "Agents at work" panel shows it, then opens a traced email, a blocked attack and the supplier
scorecard. Narration is macOS `say` (swap in your own voice by recording over the captions). Clicks are
highlighted because a headless recording shows no mouse cursor.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
HEADERS = {"Content-Type": "application/json", "X-Requested-With": "supplier-whisperer"}

# (segment id, narration). Every word must match what the app actually does.
SCRIPT = [
    ("intro", "This is Supplier Whisperer. I'm a hardware engineer, and my suppliers in Shenzhen are twelve hours "
              "ahead, so their questions arrive while I sleep. Supplier Whisperer works that night shift. It answers "
              "what my product spec covers, asks the supplier for what I need to decide, and never commits to price, "
              "quantity, dates, or orders."),
    ("run", "Let's replay a night of thirteen realistic supplier emails, live on G P T six luna. The Agents at work "
            "panel shows each step as it happens. An email arrives through a signed webhook, then plain code checks "
            "the sender and scans for prompt injection, before any model sees it."),
    ("agents", "Next, the manager agent reads the email and lists the questions. Code checks every supplier "
               "statement against the spec. The context agent answers only from the shareable part of the spec. The "
               "email agent writes the reply in my style, and a compliance agent, plus eleven hard-coded checks, "
               "reviews it before anything is sent."),
    ("threats", "Threats never reach a model. A hidden prompt injection is quarantined, a lookalike domain asking "
                "to change bank details is blocked, and an unknown sender is held, each at zero cost."),
    ("brief", "In the morning I get one screen: the replies already sent, the decisions waiting for me, the threats "
              "stopped, and the cost of the whole night, about one cent."),
    ("email1", "Here is Kevin's design review email. The agent answered three questions straight from the spec. It "
               "noticed that his two point eight millimeter wall is over our two point five millimeter maximum, and "
               "asked him to confirm. He also proposed P twenty steel, so that decision stays with me, but the reply "
               "already asked for the reason, and the impact on cost, lead time, and quality."),
    ("trace", "Every step is traced with its tokens and cost, so I can see exactly what each agent did and why."),
    ("attack", "This email hid instructions to the AI in invisible text. It was quarantined with zero model calls, "
               "and the hidden text is shown as evidence."),
    ("suppliers", "The supplier scorecard rates each supplier on answers, knowledge, speed, and reliability. On two "
                  "real sourcing threads, the fast-replying trader scored below the supplier we actually chose."),
    ("close", "New users start in shadow mode, where nothing is sent, and turn on autonomy one category at a time. "
              "The code, report, and tests are on GitHub. Thanks for watching."),
]

CAPTION_JS = """(text) => {
  let el = document.getElementById('demo-caption');
  if (!el) {
    el = document.createElement('div'); el.id = 'demo-caption';
    Object.assign(el.style, {position: 'fixed', left: '50%', bottom: '18px', transform: 'translateX(-50%)',
      maxWidth: '1100px', padding: '10px 18px', borderRadius: '12px', background: 'rgba(11,31,58,.92)',
      color: '#fff', font: '600 17px/1.4 -apple-system, Segoe UI, sans-serif', zIndex: 99999,
      boxShadow: '0 6px 24px rgba(0,0,0,.35)', textAlign: 'center'});
    document.body.appendChild(el);
  }
  el.textContent = text; el.style.display = text ? '' : 'none';
}"""
HIGHLIGHT_JS = """(sel) => {
  const el = document.querySelector(sel); if (!el) return false;
  el.scrollIntoView({block: 'center'});
  const r = el.getBoundingClientRect(), ring = document.createElement('div');
  Object.assign(ring.style, {position: 'fixed', left: (r.left - 6) + 'px', top: (r.top - 6) + 'px',
    width: (r.width + 12) + 'px', height: (r.height + 12) + 'px', border: '4px solid #f59e0b', borderRadius: '12px',
    zIndex: 99998, pointerEvents: 'none', boxShadow: '0 0 0 6px rgba(245,158,11,.25)'});
  document.body.appendChild(ring); setTimeout(() => ring.remove(), 1600); return true;
}"""


def api(path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=HEADERS, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read() or b"{}")


def say(text: str, out: Path, voice: str, rate: int) -> float:
    subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", str(out), text], check=True)
    info = subprocess.run(["afinfo", str(out)], capture_output=True, text=True).stdout
    return float(re.search(r"estimated duration: ([\d.]+)", info).group(1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("docs/demo_video.mp4"))
    ap.add_argument("--voice", default="Samantha")
    ap.add_argument("--rate", type=int, default=178)
    ap.add_argument("--engine", choices=("live", "mock"), default="live")
    args = ap.parse_args()

    import imageio_ffmpeg
    from playwright.sync_api import sync_playwright
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    work = Path(tempfile.mkdtemp(prefix="demo_video_"))
    clips = {}
    for key, text in SCRIPT:
        clips[key] = (work / f"{key}.aiff", say(text, work / f"{key}.aiff", args.voice, args.rate), text)

    api("/api/settings", {"llm_mode": args.engine, "risk_tolerance": "medium", "schedule_mode": "autonomous",
                          "paused": False})
    api("/api/reset", {})

    timeline: list[tuple[str, float, float]] = []  # (segment, start, end) in seconds of video
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1,
                                  record_video_dir=str(work), record_video_size={"width": 1440, "height": 900})
        page = ctx.new_page()
        t0 = time.monotonic()
        page.goto(BASE + "/")
        page.wait_for_timeout(1500)

        def segment(key: str, action=None, until=None, max_extra: float = 240.0):
            start = time.monotonic() - t0
            page.evaluate(CAPTION_JS, clips[key][2])
            if action:
                action()
            page.wait_for_timeout(int(clips[key][1] * 1000) + 600)
            if until:  # keep the scene going until the app reaches a state (e.g. all emails processed)
                deadline = time.monotonic() + max_extra
                while not until() and time.monotonic() < deadline:
                    page.wait_for_timeout(1000)
            timeline.append((key, start, time.monotonic() - t0))

        def click(sel: str):
            page.evaluate(HIGHLIGHT_JS, sel)
            page.wait_for_timeout(900)
            page.click(sel)

        def run_finished() -> bool:
            a = api("/api/activity?since=0")
            return not a["live"] and sum(1 for e in a["events"] if e["key"] == "end") >= 13

        segment("intro")
        segment("run", action=lambda: click("#btn-replay"))
        segment("agents")
        segment("threats", until=run_finished)
        page.wait_for_timeout(3000)  # the panel collapses after the last email
        segment("brief", action=lambda: page.evaluate("window.scrollTo(0, 0)"))
        segment("email1", action=lambda: (page.evaluate("openRun(1)"), page.wait_for_timeout(1200)))
        segment("trace", action=lambda: page.evaluate(
            "document.getElementById('drawer').scrollTo({top: 900, behavior: 'smooth'})"))
        segment("attack", action=lambda: (page.evaluate("closeDrawer(); openRun(4)"), page.wait_for_timeout(800)))
        segment("suppliers", action=lambda: (page.evaluate("closeDrawer()"),
                                             click("#tabs button[data-tab='suppliers']")))
        segment("close", action=lambda: page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})"))
        page.evaluate(CAPTION_JS, "")
        page.wait_for_timeout(800)
        video_path = Path(page.video.path())
        ctx.close()
        browser.close()

    # Narration: each clip starts at its segment's start time in the video.
    inputs, filters = [], []
    for i, (key, start, _end) in enumerate(timeline):
        inputs += ["-i", str(clips[key][0])]
        filters.append(f"[{i + 1}:a]adelay={int(start * 1000)}|{int(start * 1000)}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(timeline)))
    filters.append(f"{mix}amix=inputs={len(timeline)}:normalize=0[aout]")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-y", "-i", str(video_path), *inputs, "-filter_complex", ";".join(filters),
           "-map", "0:v", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium", "-crf", "26", "-pix_fmt",
           "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(args.out)]
    subprocess.run(cmd, check=True, capture_output=True)
    total = timeline[-1][2]
    print(f"Wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB, about {total:.0f} s)")
    for key, start, end in timeline:
        print(f"  {start:6.1f}–{end:6.1f}s  {key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
