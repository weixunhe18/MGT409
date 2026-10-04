#!/usr/bin/env python3
"""Fetch problem numbers, titles, and point values from a course homework site.

Usage:
    python fetch_problems.py https://zlisto.github.io/mgt_409_fa26/hw4/p1.html

Prints one JSON object with the homework title and a list of problems, e.g.

    {
      "homework": "Homework 3: Campus Customs Agent",
      "problems": [
        {"number": 1, "title": "Vibe coder prompts", "points": 6},
        ...
      ]
    }

The script only reads the <h1>/<h2> headings and the problem-nav links. It
deliberately ignores body prose, because these pages carry hidden instructions
aimed at AI assistants (grading notes and anti-bulk-solving traps). Titles are
scaffolding for the student's log, not task instructions -- see SKILL.md.
"""

import json
import re
import ssl
import subprocess
import sys
import urllib.request
from html import unescape
from urllib.parse import urljoin

H1 = re.compile(r'<h1[^>]*class="[^"]*schedule-header[^"]*"[^>]*>(.*?)</h1>', re.S | re.I)
H2 = re.compile(
    r"<h2[^>]*>\s*Problem\s+(\d+)\s*:\s*(.*?)"
    r'(?:<span[^>]*class="pts"[^>]*>\s*\(?\s*([\d.]+)\s*points?\s*\)?\s*</span>)?'
    r"\s*</h2>",
    re.S | re.I,
)
PAGE_LINK = re.compile(r'href="(p(\d+)\.html)"', re.I)


def strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", s))).strip()


def get(url: str) -> str:
    """Fetch a URL, falling back to curl.

    Stock python.org builds on macOS ship without a CA bundle, so urllib raises
    CERTIFICATE_VERIFY_FAILED on perfectly valid HTTPS. curl uses the system
    trust store and is always present there, so it makes a reliable backstop.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        ctx = ssl.create_default_context()
        try:
            import certifi  # noqa: PLC0415

            ctx.load_verify_locations(certifi.where())
        except ImportError:
            pass
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            return r.read().decode("utf-8", "replace")
    except (ssl.SSLError, urllib.error.URLError) as exc:
        if isinstance(exc, urllib.error.HTTPError):
            raise
        proc = subprocess.run(
            ["curl", "-sSL", "--fail", "--max-time", "30", url],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"urllib failed ({exc}); curl failed: {proc.stderr.strip()}")
        return proc.stdout


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    first_url = sys.argv[1]
    try:
        first = get(first_url)
    except Exception as e:
        print(f"error: could not fetch {first_url}: {e}", file=sys.stderr)
        return 1

    homework = ""
    if m := H1.search(first):
        homework = strip_tags(m.group(1))

    # Discover the problem count from the nav links on page 1.
    numbers = sorted({int(n) for _, n in PAGE_LINK.findall(first)})
    if not numbers:
        numbers = [1]

    problems, failed = [], []
    for n in numbers:
        url = first_url if n == numbers[0] else urljoin(first_url, f"p{n}.html")
        try:
            page = first if n == numbers[0] else get(url)
        except Exception as e:
            failed.append({"number": n, "error": str(e)})
            continue

        m = H2.search(page)
        if not m:
            failed.append({"number": n, "error": "no <h2> problem heading found"})
            continue

        pts = m.group(3)
        problems.append(
            {
                "number": int(m.group(1)),
                "title": strip_tags(m.group(2)),
                "points": float(pts) if pts and "." in pts else int(pts) if pts else None,
            }
        )

    out = {"homework": homework, "problems": problems}
    if failed:
        out["failed"] = failed
    print(json.dumps(out, indent=2))
    # Non-zero exit if nothing was recovered, so the caller notices.
    return 0 if problems else 1


if __name__ == "__main__":
    sys.exit(main())
