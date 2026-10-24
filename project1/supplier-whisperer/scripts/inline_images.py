"""Embed local images into an HTML file as base64 so it opens anywhere with every screenshot visible
(course rule for report.html and slides.html).

    python scripts/inline_images.py docs/report_src.html report.html
    python scripts/inline_images.py docs/slides_src.html slides.html
"""

from __future__ import annotations

import base64
import mimetypes
import re
import sys
from pathlib import Path

IMG_RE = re.compile(r"""(<img\b[^>]*?\bsrc=)(["'])(?!data:|https?:)([^"']+)\2""", re.IGNORECASE)


def inline(src: Path, dst: Path) -> tuple[int, list[str]]:
    html = src.read_text(encoding="utf-8")
    count, missing = 0, []

    def replace(match: re.Match) -> str:
        nonlocal count
        path = (src.parent / match.group(3)).resolve()
        if not path.is_file():
            missing.append(match.group(3))
            return match.group(0)
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        count += 1
        return f"{match.group(1)}{match.group(2)}data:{mime};base64,{data}{match.group(2)}"

    dst.write_text(IMG_RE.sub(replace, html), encoding="utf-8")
    return count, missing


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    count, missing = inline(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"Embedded {count} image(s) into {sys.argv[2]}")
    for item in missing:
        print(f"  MISSING: {item}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
