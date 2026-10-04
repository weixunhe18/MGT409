"""Tools and helpers for the Campus Customs agent.

The identify ability is built around one idea: never compare the query photo against
catalogue photos one pair at a time. That would be 102 vision calls per query. Instead:

1. The agent looks at the query photo once and describes it in the catalogue's own
   vocabulary (clothing type, color, text on garment).
2. `shortlist_catalogue` compares that description against catalogue.json **locally** —
   plain text scoring, no API calls, no images.
3. `compare_candidate_photos` sends the query photo plus the handful of surviving
   candidates in a *single* call, capped at MAX_CANDIDATE_IMAGES product photos.

So a query costs two vision calls regardless of catalogue size, and the second one
never carries more than 10 product images.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from PIL import Image

from models import (
    AdQualityScores,
    AuditEntry,
    CandidateMatch,
    Catalogue,
    CatalogueEntry,
    ClothingType,
    CustomerProfile,
    GarmentObservation,
)

HW_DIR = Path(__file__).resolve().parent
CATALOGUE_PATH = HW_DIR / "output" / "catalogue.json"
PRODUCTS_DIR = HW_DIR / "data" / "products"
AUDIT_PATH = HW_DIR / "output" / "audit_trail.json"

MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-5.6-terra")

# The assignment caps a single call at 10 product images. Six keeps well under that while
# still giving the model real alternatives to choose between, and keeps the call cheap.
MAX_CANDIDATE_IMAGES = 6
HARD_IMAGE_CAP = 10

MAX_IMAGE_PX = 512
JPEG_QUALITY = 80

# Frames sampled from an ad video. The test ad is 9 seconds / 217 frames, so 8 evenly
# spaced stills is roughly one per second — enough to catch every shot change without
# paying for 217 nearly identical images.
FRAMES_PER_VIDEO = 8

# How much of a tool result to keep in the audit trail. Enough to see why a decision was
# made, short enough that the file stays readable after dozens of runs.
AUDIT_RESULT_CHARS = 300

# A candidate has to clear this to be worth showing the agent. Matching the garment type
# alone scores 2.0, so this floor admits real leads while rejecting products that share
# only a colour or a stray description word — the difference between an empty shortlist
# and six misleading suggestions when the photo contains no Campus Customs product.
MIN_CANDIDATE_SCORE = 1.5

# Words that appear on nearly every garment and so carry no discriminating signal.
STOPWORDS = {"yale", "university", "college", "the", "of", "and", "a", "an", "school"}


# --------------------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------------------


def load_api_key() -> str:
    """Read the Portkey key, preferring a homework-local .env over the course-root one."""
    for candidate in (HW_DIR / ".env", HW_DIR.parent / ".env"):
        if candidate.exists():
            load_dotenv(candidate)
    key = os.environ.get("PORTKEY_API_KEY") or os.environ.get("portkey_api_key")
    if not key:
        raise RuntimeError(
            "PORTKEY_API_KEY is missing. Copy .env.example to .env and add your key."
        )
    return key


def make_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=load_api_key(),
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-provider": "openai"},
    )


def encode_image(path: Path, max_px: int = MAX_IMAGE_PX) -> str:
    """Downscale an image and return it base64-encoded, as in the catalogue build."""
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=JPEG_QUALITY)
    return base64.b64encode(buf.getvalue()).decode()


@lru_cache(maxsize=1)
def load_catalogue() -> Catalogue:
    """Load catalogue.json once per process."""
    if not CATALOGUE_PATH.exists():
        raise RuntimeError(
            f"{CATALOGUE_PATH} not found. Run `python build_catalogue.py` first."
        )
    return Catalogue.model_validate_json(CATALOGUE_PATH.read_text())


# --------------------------------------------------------------------------------------
# Step 2 — local shortlist (no API calls, no images)
# --------------------------------------------------------------------------------------


def coerce_clothing_type(value: str) -> ClothingType:
    """Map a free-text garment name onto the catalogue's enum.

    The agent describes what it sees in its own words ("hooded sweatshirt", "1/4 zip"),
    but the catalogue only knows fixed categories. Failing the whole run over a wording
    mismatch would be silly, so anything unrecognised becomes OTHER and the text still
    contributes through the description field.
    """
    raw = value.strip().lower()
    for member in ClothingType:
        if raw == member.value:
            return member

    # Checked in order, most specific first, because these descriptions overlap: a
    # "full zip hoodie" is a full-zip, and a "hooded sweatshirt" is a hoodie even though
    # it also contains the word "sweatshirt". Crewneck sits last as the generic fallback
    # for pullover sweatshirts with no other distinguishing word.
    aliases: tuple[tuple[ClothingType, tuple[str, ...]], ...] = (
        (ClothingType.FULL_ZIP, ("full zip", "full-zip", "zip-up", "zip up")),
        (ClothingType.QUARTER_ZIP, ("quarter zip", "quarter-zip", "quarter", "1/4", "half zip")),
        (ClothingType.HOODIE, ("hoodie", "hooded", "hoody", "hood")),
        (ClothingType.LONG_SLEEVE, ("long sleeve", "long-sleeve")),
        (ClothingType.T_SHIRT, ("t-shirt", "t shirt", "tshirt", "tee")),
        (ClothingType.FLEECE, ("fleece",)),
        (ClothingType.JACKET, ("jacket", "bomber")),
        (ClothingType.SWEATER, ("sweater", "knit")),
        (ClothingType.CREWNECK, ("crewneck", "crew neck", "crew", "sweatshirt", "pullover")),
    )
    # Whole-word matching, not substring: "sweatshirt" happens to contain "tshirt", which
    # would otherwise classify every crewneck as a t-shirt.
    for member, alias_group in aliases:
        if any(re.search(rf"\b{re.escape(alias)}\b", raw) for alias in alias_group):
            return member
    return ClothingType.OTHER


def tokenize(text: str) -> set[str]:
    """Lowercase word set with common Yale boilerplate and short filler words removed.

    The length floor drops "on", "in", "at" and friends. Without it, a photo of a dog
    "sitting on grass" scores against every product whose description says "crest on the
    left chest" — noise that would put six irrelevant candidates in front of the agent.
    """
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def score_entry(observation: GarmentObservation, entry: CatalogueEntry) -> tuple[float, str]:
    """Score one catalogue product against the observed garment.

    The weights encode how much each feature actually narrows this catalogue. Printed
    text dominates because almost every product here is a grey or navy sweatshirt whose
    only distinguishing feature is its print — colour barely discriminates at all, since
    90 of the 102 products are one of those two colours.
    """
    score = 0.0
    reasons: list[str] = []

    query_text = tokenize(observation.text_on_garment)
    entry_text = tokenize(entry.text_on_garment)
    if query_text and entry_text:
        overlap = query_text & entry_text
        if overlap:
            # Jaccard over the distinctive words, weighted heavily.
            similarity = len(overlap) / len(query_text | entry_text)
            score += 6.0 * similarity
            reasons.append(f"text overlap {sorted(overlap)}")

    if observation.clothing_type == entry.clothing_type:
        score += 2.0
        reasons.append(f"same garment type ({entry.clothing_type.value})")

    if observation.color and observation.color.lower() in entry.color.lower():
        score += 1.0
        reasons.append(f"same colour ({entry.color})")

    query_desc = tokenize(observation.description)
    entry_desc = tokenize(entry.description) | tokenize(entry.special_note)
    if query_desc and entry_desc:
        shared = query_desc & entry_desc
        if shared:
            score += 2.0 * len(shared) / len(query_desc | entry_desc)
            reasons.append(f"description overlap {sorted(shared)[:4]}")

    return score, "; ".join(reasons) or "no shared features"


def shortlist_catalogue(
    observation: GarmentObservation, limit: int = MAX_CANDIDATE_IMAGES
) -> list[CandidateMatch]:
    """Rank the whole catalogue locally and return the best few candidates.

    This is the step that makes the constraint work: scoring 102 text records costs
    nothing, so the expensive visual comparison only ever sees a handful of products.
    """
    catalogue = load_catalogue()
    scored = []
    for entry in catalogue.entries:
        score, reason = score_entry(observation, entry)
        if score >= MIN_CANDIDATE_SCORE:
            scored.append(
                CandidateMatch(product_id=entry.product_id, score=round(score, 3), reason=reason)
            )

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[: min(limit, HARD_IMAGE_CAP)]


def catalogue_entry(product_id: str) -> CatalogueEntry | None:
    return next(
        (e for e in load_catalogue().entries if e.product_id == product_id), None
    )


# --------------------------------------------------------------------------------------
# Step 3 — one visual comparison against the shortlist
# --------------------------------------------------------------------------------------


async def compare_candidate_photos(query_image: Path, product_ids: list[str]) -> str:
    """Show the query photo and the shortlisted products side by side in ONE call.

    Returns the model's plain-text verdict. Raises if asked to send more than the
    assignment's 10-image limit, so the constraint can't be violated by accident.
    """
    if not product_ids:
        return "No candidates to compare."
    if len(product_ids) > HARD_IMAGE_CAP:
        raise ValueError(
            f"refusing to send {len(product_ids)} product images in one call; "
            f"the limit is {HARD_IMAGE_CAP}"
        )

    content: list[dict] = [
        {
            "type": "input_text",
            "text": (
                "The first image is a customer photo. The remaining images are candidate "
                "products from our catalogue, listed in order.\n\n"
                "Decide whether the garment in the customer photo is one of these products. "
                "Answer with the product id and a one-sentence reason, or say NO_MATCH if "
                "the customer photo does not show any of them. Judge by the printed design "
                "and garment shape; lighting and angle will differ.\n\n"
                "Candidates in order: " + ", ".join(product_ids)
            ),
        },
        {
            "type": "input_image",
            "image_url": f"data:image/jpeg;base64,{encode_image(query_image)}",
        },
    ]

    for product_id in product_ids:
        entry = catalogue_entry(product_id)
        if entry is None:
            continue
        photo = PRODUCTS_DIR / entry.image_file
        if not photo.exists():
            continue
        content.append(
            {
                "type": "input_text",
                "text": f"Candidate: {product_id}",
            }
        )
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{encode_image(photo)}",
            }
        )

    client = make_client()
    try:
        response = await client.responses.create(
            model=MODEL_NAME,
            input=[{"role": "user", "content": content}],
            reasoning={"effort": "none"},
            max_output_tokens=400,
        )
        return response.output_text or "No verdict returned."
    except Exception as exc:  # noqa: BLE001 - surfaced to the agent as a tool result
        # The image-safety filter occasionally rejects ordinary product shots (see
        # harness.md); the agent should degrade to its text-based shortlist, not crash.
        return f"Visual comparison unavailable ({type(exc).__name__}). Rely on the shortlist scores."


def summarize_candidates(candidates: list[CandidateMatch]) -> str:
    """Render shortlist results as JSON the agent can reason over."""
    payload = []
    for candidate in candidates:
        entry = catalogue_entry(candidate.product_id)
        payload.append(
            {
                "product_id": candidate.product_id,
                "score": candidate.score,
                "why_shortlisted": candidate.reason,
                "clothing_type": entry.clothing_type.value if entry else None,
                "color": entry.color if entry else None,
                "text_on_garment": entry.text_on_garment if entry else None,
                "description": entry.description if entry else None,
            }
        )
    return json.dumps(payload, indent=2)


# --------------------------------------------------------------------------------------
# Ad-effectiveness ability (Problem 5)
# --------------------------------------------------------------------------------------


def load_profile(path: Path) -> CustomerProfile:
    """Load a customer profile JSON written by Problem 6."""
    if not path.exists():
        raise RuntimeError(f"profile not found: {path}")
    return CustomerProfile.model_validate_json(path.read_text())


def sample_video_frames(video_path: Path, count: int = FRAMES_PER_VIDEO) -> list[str]:
    """Return `count` evenly spaced frames from a video, base64 JPEG, oldest first.

    Sampling rather than streaming the whole file is the entire cost control here: the ad
    is 217 frames at 1080p, and sending all of them would be both expensive and redundant
    since consecutive frames are nearly identical. Evenly spaced stills capture the shot
    changes, which is what a judgement about pacing and content actually needs.
    """
    import av  # imported lazily so the identify ability doesn't pay for it

    with av.open(str(video_path)) as container:
        stream = container.streams.video[0]
        total = stream.frames or 0

        if total <= 0:  # some containers don't report a frame count
            frames = [f.to_image() for f in container.decode(video=0)]
            total = len(frames)
            step = max(1, total // count)
            picked = frames[::step][:count]
        else:
            wanted = {round(i * (total - 1) / max(1, count - 1)) for i in range(count)}
            picked = [
                frame.to_image()
                for index, frame in enumerate(container.decode(video=0))
                if index in wanted
            ]

    encoded = []
    for image in picked[:count]:
        image = image.convert("RGB")
        image.thumbnail((MAX_IMAGE_PX, MAX_IMAGE_PX))
        buf = io.BytesIO()
        image.save(buf, "JPEG", quality=JPEG_QUALITY)
        encoded.append(base64.b64encode(buf.getvalue()).decode())
    return encoded


async def watch_ad_video(video_path: Path, count: int = FRAMES_PER_VIDEO) -> str:
    """Describe an ad from sampled frames, in ONE call.

    Returns a plain-text description of what happens, how it is shot, and whether it
    tells a viewer what to do next. The agent then judges that description against a
    customer profile — separating "what is in the ad" from "who it works for" keeps the
    two judgements independently checkable.
    """
    frames = sample_video_frames(video_path, count)
    if not frames:
        return "Could not read any frames from the video."

    content: list[dict] = [
        {
            "type": "input_text",
            "text": (
                f"These are {len(frames)} frames sampled evenly from a {len(frames)}-shot "
                "advertisement for Campus Customs, a Yale apparel store. They are in "
                "chronological order.\n\n"
                "Describe, in a short paragraph each:\n"
                "1. What happens — setting, people, what they wear, what the ad depicts.\n"
                "2. Production craft — camera work, lighting, styling, how polished it looks.\n"
                "3. Tone and voice — what feeling it goes for, and whether it reads as "
                "authentic or as a corporate sales pitch.\n"
                "4. Call to action — any on-screen text, brand name, website, price or "
                "instruction telling a viewer what to do next. Say plainly if there is none.\n"
                "5. Argument — any reason a viewer is given to buy, beyond mood and image.\n\n"
                "Report only what is visible. You cannot hear the soundtrack, so do not "
                "guess at narration or music."
            ),
        }
    ]
    for frame in frames:
        content.append(
            {"type": "input_image", "image_url": f"data:image/jpeg;base64,{frame}"}
        )

    client = make_client()
    try:
        response = await client.responses.create(
            model=MODEL_NAME,
            input=[{"role": "user", "content": content}],
            reasoning={"effort": "none"},
            max_output_tokens=900,
        )
        return response.output_text or "No description returned."
    except Exception as exc:  # noqa: BLE001 - surfaced to the agent as a tool result
        return f"Could not analyse the video ({type(exc).__name__}: {exc})."


def weighted_fit(scores: AdQualityScores, profile: CustomerProfile) -> float:
    """Combine ad scores with a profile's priorities into a 0-100 fit.

    Computed here rather than asked of the model: the same ad and profile should always
    produce the same number, and a weighted average is exactly the kind of arithmetic a
    language model has no business improvising. The weights are what make the result
    profile-specific — a polished ad with no call to action scores very differently for
    a student who barely cares about polish than for a parent who needs the CTA.
    """
    priorities = profile.ad_priorities
    pairs = (
        (scores.production_quality, priorities.production_quality),
        (scores.thoughtful_voice, priorities.thoughtful_voice),
        (scores.clear_call_to_action, priorities.clear_call_to_action),
        (scores.sound_logic, priorities.sound_logic),
    )
    earned = sum(score * weight for score, weight in pairs)
    possible = sum(5 * weight for _, weight in pairs)
    return round(100 * earned / possible, 1)


# --------------------------------------------------------------------------------------
# Audit trail (Problem 8)
# --------------------------------------------------------------------------------------


def append_audit(entry: AuditEntry) -> None:
    """Append one audit record to output/audit_trail.json, preserving what is there.

    Read-modify-write rather than truncate: the file accumulates across every run of
    every ability, so a reader can reconstruct what the agent did last Tuesday. Each
    call re-reads the file, which is fine at this volume and means a crash mid-run
    loses at most the current iteration.

    A corrupt or hand-edited trail is never allowed to take down a run — the agent's
    job is to answer the customer, and losing an audit record is the lesser failure.
    """
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing: list[dict] = []
    if AUDIT_PATH.exists():
        try:
            loaded = json.loads(AUDIT_PATH.read_text())
            if isinstance(loaded, list):
                existing = loaded
        except (json.JSONDecodeError, OSError):
            existing = []

    existing.append(entry.model_dump(mode="json"))
    try:
        AUDIT_PATH.write_text(json.dumps(existing, indent=2))
    except OSError as exc:
        print(f"warning: could not write audit trail: {exc}", file=sys.stderr)


def summarize_for_audit(text: str, limit: int = AUDIT_RESULT_CHARS) -> str:
    """Shorten a tool result to something auditable.

    Tool results here include base64 verdicts and 100-entry catalogue dumps. Storing
    them whole would make the trail unreadable and enormous; the first few hundred
    characters are what actually show why a decision was made.
    """
    flattened = " ".join(str(text).split())
    if len(flattened) <= limit:
        return flattened
    return flattened[:limit] + f"… [{len(flattened) - limit} more chars]"
