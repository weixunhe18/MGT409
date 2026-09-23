"""Screen capture helpers for the immersive browser agent."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any

import mss
from PIL import Image


WINDOW_TITLE = "Browser agent"


def _browser_window_bounds() -> dict[str, int] | None:
    """Return the Browser agent window bounds on macOS when Quartz is available."""
    try:
        import Quartz  # type: ignore[import-not-found]
    except ImportError:
        return None

    options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    windows = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID) or []
    candidates: list[dict[str, int]] = []
    for window in windows:
        owner = window.get(Quartz.kCGWindowOwnerName, "")
        name = window.get(Quartz.kCGWindowName, "")
        if WINDOW_TITLE not in (owner, name) and WINDOW_TITLE not in f"{owner} {name}":
            continue
        bounds = window.get(Quartz.kCGWindowBounds)
        if not bounds:
            continue
        candidates.append(
            {
                "left": int(bounds.get("X", 0)),
                "top": int(bounds.get("Y", 0)),
                "width": int(bounds.get("Width", 0)),
                "height": int(bounds.get("Height", 0)),
            }
        )
    return max(candidates, key=lambda item: item["width"] * item["height"]) if candidates else None


def capture_screen(region: str = "window") -> dict[str, Any]:
    """Capture the Browser agent window, falling back to the primary monitor."""
    with mss.mss() as grabber:
        bounds = _browser_window_bounds() if region == "window" else None
        if bounds and bounds["width"] > 0 and bounds["height"] > 0:
            monitor = bounds
            captured_region = "window"
        else:
            monitor = grabber.monitors[1]
            captured_region = "full"

        raw = grabber.grab(monitor)
        image = Image.frombytes("RGB", raw.size, raw.rgb)
        output = BytesIO()
        image.save(output, format="PNG", optimize=True)
        return {
            "data": output.getvalue(),
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "region": captured_region,
            "width": image.width,
            "height": image.height,
        }
