"""Build the Campus Customs product catalogue from the photos in data/products/.

Reads every product photo, asks a vision model to describe it, and writes the
structured result to output/catalogue.json.

Three things keep this fast (see output/harness.md for the measured numbers):

1. Concurrency — the work is almost entirely time spent waiting on API responses,
   so requests go out in parallel instead of one-at-a-time. A semaphore caps how
   many are in flight so we stay under the rate limit.
2. Downscaling — product shots get resized before upload. Fewer vision tokens per
   image means a cheaper and faster call, and the garment is still perfectly legible.
3. Caching — results are keyed by image content, so re-running after a prompt tweak
   only pays for images whose inputs actually changed.

Usage:
    python build_catalogue.py                    # build everything
    python build_catalogue.py --limit 5          # try a handful first
    python build_catalogue.py --sequential       # one-at-a-time, for timing comparison
    python build_catalogue.py --no-cache         # force fresh API calls
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import io
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from PIL import Image

from models import Catalogue, CatalogueEntry, CatalogueFailure

HW_DIR = Path(__file__).resolve().parent
PRODUCTS_DIR = HW_DIR / "data" / "products"
OUTPUT_PATH = HW_DIR / "output" / "catalogue.json"
CACHE_DIR = HW_DIR / ".cache" / "catalogue"

MODEL = "gpt-5.6-luna"
MAX_CONCURRENCY = 12
MAX_ATTEMPTS = 4
# The image-safety filter is intermittent (see harness.md), so a rejection is worth
# retrying — but only briefly, since a genuinely blocked photo would otherwise spend
# the full backoff schedule arriving at the same answer.
CONTENT_POLICY_ATTEMPTS = 2

# (max pixels, JPEG quality) tried in order. The first is the normal setting; the second
# is a fallback for photos the upstream image-safety filter rejects. Two of the 102 product
# shots — both residential-college crests on plain sweatshirts — hit
# content_policy_violation on some runs. They are ordinary catalogue photos, so the filter
# is false-positiving on the heraldry. Anything still refused after both variants and their
# retries is recorded as a failure rather than worked around further.
IMAGE_VARIANTS = ((512, 80), (384, 70))

# Bumping this invalidates cached entries, so a prompt change actually takes effect.
PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """\
You catalogue Yale-branded merchandise for Campus Customs, a campus apparel store.

Look at the product photo and record what you can actually see. Accuracy matters more
than detail here: this catalogue is later used to match a customer's photo against the
product line, so a confident wrong answer is worse than a plain one.

- clothing_type: pick the closest category. A hooded pullover is a hoodie even if the
  product name says "sweatshirt"; a hooded garment with a full-length zipper is full-zip.
- color: the dominant color of the garment itself, not the background or the print.
  Use one simple word.
- special_note: the theme — a sport, a school or residential college, or a family angle
  like dad or mom. Use "none" for unbranded garments.
- text_on_garment: copy any printed words exactly as they appear, including the school
  name. Leave empty if the garment has no text.
"""


def load_api_key() -> str:
    """Read the Portkey key, preferring a local .env over the course-root one."""
    for candidate in (HW_DIR / ".env", HW_DIR.parent / ".env"):
        if candidate.exists():
            load_dotenv(candidate)
    try:
        return os.environ["PORTKEY_API_KEY"]
    except KeyError:
        sys.exit(
            "error: PORTKEY_API_KEY is not set.\n"
            "Copy .env.example to .env and add your key, or set it in the course-root .env."
        )


def prepare_image(path: Path, max_px: int, quality: int) -> tuple[str, str]:
    """Downscale a product photo and return (base64 JPEG, cache key).

    The cache key covers the image bytes, the encoding settings, the model, the prompt,
    and the schema, so any change that would alter the answer produces a different key.
    """
    raw = path.read_bytes()

    with Image.open(io.BytesIO(raw)) as im:
        im = im.convert("RGB")
        im.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=quality)
    encoded = base64.b64encode(buf.getvalue()).decode()

    fingerprint = hashlib.sha256(
        raw
        + f"{max_px}x{quality}".encode()
        + MODEL.encode()
        + PROMPT_VERSION.encode()
        + json.dumps(CatalogueEntry.model_json_schema(), sort_keys=True).encode()
    ).hexdigest()
    return encoded, fingerprint


def read_cache(key: str) -> CatalogueEntry | None:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        return CatalogueEntry.model_validate_json(path.read_text())
    except Exception:
        # A stale or corrupt cache entry should never break a build.
        return None


def write_cache(key: str, entry: CatalogueEntry) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(entry.model_dump_json(indent=2))


def is_permanent(exc: Exception) -> bool:
    """True if retrying this error is pointless — a malformed request, a bad model ID.

    Content-policy rejections are handled separately: they come back as 400s but are
    intermittent, so the caller retries those rather than giving up here.
    """
    status = getattr(exc, "status_code", None)
    return isinstance(status, int) and 400 <= status < 500 and status != 429


async def describe_image(
    client: AsyncOpenAI, path: Path, use_cache: bool, stats: dict[str, int]
) -> CatalogueEntry | CatalogueFailure:
    """Turn one product photo into a catalogue entry, trying each encoding variant."""
    last: CatalogueFailure | None = None
    for max_px, quality in IMAGE_VARIANTS:
        result = await describe_at_size(client, path, max_px, quality, use_cache, stats)
        if isinstance(result, CatalogueEntry):
            return result
        last = result
        if "content_policy" not in result.reason:
            break  # only the safety filter is worth re-encoding for
    assert last is not None
    stats["failed"] += 1
    print(f"\n  failed: {path.name}: {last.reason}", file=sys.stderr)
    return last


async def describe_at_size(
    client: AsyncOpenAI,
    path: Path,
    max_px: int,
    quality: int,
    use_cache: bool,
    stats: dict[str, int],
) -> CatalogueEntry | CatalogueFailure:
    """One catalogue attempt at a specific image encoding, with retries and caching."""
    encoded, key = await asyncio.to_thread(prepare_image, path, max_px, quality)

    if use_cache and (cached := read_cache(key)) is not None:
        stats["cached"] += 1
        return cached

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await client.responses.parse(
                model=MODEL,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": f"Catalogue this product. Filename: {path.name}",
                            },
                            {
                                "type": "input_image",
                                "image_url": f"data:image/jpeg;base64,{encoded}",
                            },
                        ],
                    },
                ],
                text_format=CatalogueEntry,
                reasoning={"effort": "none"},
                max_output_tokens=600,
            )
            entry = response.output_parsed
            if entry is None:
                raise ValueError("model returned no parsed output")

            # The model sees the filename but shouldn't be trusted to echo it back.
            entry.product_id = path.stem
            entry.image_file = path.name

            stats["tokens"] += getattr(response.usage, "total_tokens", 0) or 0
            stats["fetched"] += 1
            write_cache(key, entry)
            return entry

        except Exception as exc:
            # A content-policy rejection is flaky rather than final, so it gets its own
            # (shorter) retry budget instead of being treated as a permanent 4xx.
            policy_block = "content_policy" in str(exc)
            limit = CONTENT_POLICY_ATTEMPTS if policy_block else MAX_ATTEMPTS
            if attempt >= limit or (is_permanent(exc) and not policy_block):
                return CatalogueFailure(
                    image_file=path.name, reason=f"{type(exc).__name__}: {exc}"
                )
            stats["retries"] += 1
            if os.environ.get("CATALOGUE_DEBUG"):
                print(f"\n  retry {attempt} {path.name}: {type(exc).__name__}", file=sys.stderr)
            # Exponential backoff with jitter, so retries don't stampede the API together.
            await asyncio.sleep(2**attempt * 0.5 + random.uniform(0, 0.5))

    return CatalogueFailure(image_file=path.name, reason="retries exhausted")


async def build(
    paths: list[Path], concurrency: int, use_cache: bool
) -> tuple[list[CatalogueEntry], list[CatalogueFailure]]:
    client = AsyncOpenAI(
        api_key=load_api_key(),
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-provider": "openai"},
        max_retries=0,  # retries are handled above, with our own backoff
    )
    stats = {"cached": 0, "fetched": 0, "failed": 0, "tokens": 0, "retries": 0}
    semaphore = asyncio.Semaphore(concurrency)
    done = 0

    async def worker(path: Path) -> CatalogueEntry | CatalogueFailure:
        nonlocal done
        async with semaphore:
            result = await describe_image(client, path, use_cache, stats)
        done += 1
        print(f"\r  {done}/{len(paths)} images", end="", flush=True)
        return result

    results = await asyncio.gather(*(worker(p) for p in paths))
    print()
    print(
        f"  {stats['fetched']} from API, {stats['cached']} from cache, "
        f"{stats['failed']} failed, {stats['retries']} retries, {stats['tokens']:,} tokens"
    )
    return (
        [r for r in results if isinstance(r, CatalogueEntry)],
        [r for r in results if isinstance(r, CatalogueFailure)],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, help="only process N photos")
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="skip the first N photos; use with --limit to benchmark on unseen images",
    )
    parser.add_argument(
        "--concurrency", type=int, default=MAX_CONCURRENCY, help="max requests in flight"
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="process one image at a time (to measure the speedup)",
    )
    parser.add_argument("--no-cache", action="store_true", help="ignore cached results")
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH, help="output path")
    args = parser.parse_args()

    paths = sorted(
        p for p in PRODUCTS_DIR.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    if not paths:
        sys.exit(f"error: no product photos found in {PRODUCTS_DIR}")
    paths = paths[args.offset :]
    if args.limit:
        paths = paths[: args.limit]
    if not paths:
        sys.exit("error: --offset/--limit selected no photos")

    concurrency = 1 if args.sequential else args.concurrency
    mode = "sequential" if concurrency == 1 else f"concurrent (max {concurrency} in flight)"
    print(f"Cataloguing {len(paths)} photos — {mode}")

    started = time.perf_counter()
    entries, failures = asyncio.run(build(paths, concurrency, use_cache=not args.no_cache))
    elapsed = time.perf_counter() - started

    catalogue = Catalogue(
        generated_at=datetime.now(timezone.utc),
        model=MODEL,
        entry_count=len(entries),
        entries=entries,
        failures=failures,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(catalogue.model_dump_json(indent=2))

    rate = len(paths) / elapsed if elapsed else 0
    print(f"Wrote {len(entries)} entries to {args.out} in {elapsed:.1f}s ({rate:.1f} images/s)")
    if failures:
        print(f"{len(failures)} photo(s) could not be catalogued, recorded in the failures list:")
        for failure in failures:
            print(f"  - {failure.image_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
