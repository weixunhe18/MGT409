"""Campus Customs agent — entry point.

Identify whether a Campus Customs product appears in a photo:

    python agent.py --image "data/test_images/image_01_true.jpeg"

Several images at once, all written to one results file:

    python agent.py --image data/test_images/*.jpeg

The agent sees the query photo directly, then uses two tools from tools.py: a local
catalogue search that costs nothing, and a single visual comparison against the few
candidates that survive it. See tools.py for why it is built that way.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Keep the CLI output to the identification result itself.
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic_ai import Agent, BinaryContent, RunContext
from pydantic_ai.messages import (
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

import tools
from models import (
    AdEffectivenessResult,
    AuditEntry,
    AdEffectivenessRun,
    AdQualityScores,
    CandidateMatch,
    CustomerProfile,
    GarmentObservation,
    IdentifyResult,
    IdentifyRun,
)

HW_DIR = Path(__file__).resolve().parent
PROMPT_PATH = HW_DIR / "prompts" / "prompt.md"
IDENTIFY_OUTPUT = HW_DIR / "output" / "identify_product.json"
AD_OUTPUT = HW_DIR / "output" / "ad_effectiveness.json"

# The agent needs a look, a search, a comparison, and an answer. A few spare iterations
# cover a retry; an unbounded loop would just burn money on a confused run.
MAX_ITERATIONS = 8


class IdentifyDeps:
    """Per-run state the tools need: which photo we are looking at, and what we found."""

    def __init__(self, image_path: Path) -> None:
        self.image_path = image_path
        self.observation: GarmentObservation | None = None
        self.candidates: list[CandidateMatch] = []


class AdDeps:
    """Per-run state for judging one ad against one customer profile."""

    def __init__(self, video_path: Path, profile: CustomerProfile) -> None:
        self.video_path = video_path
        self.profile = profile
        self.scores: AdQualityScores | None = None
        self.fit: float | None = None
        self.frames_sampled: int = 0


def build_agent() -> Agent[IdentifyDeps, IdentifyResult]:
    """Wire the PydanticAI agent to the Portkey-hosted model and register its tools."""
    client = tools.make_client()
    model = OpenAIResponsesModel(
        tools.MODEL_NAME, provider=OpenAIProvider(openai_client=client)
    )

    agent = Agent(
        model,
        deps_type=IdentifyDeps,
        output_type=IdentifyResult,
        system_prompt=PROMPT_PATH.read_text(),
        retries=2,
        name="campus-customs-agent",
    )

    @agent.tool
    async def search_catalogue(
        ctx: RunContext[IdentifyDeps],
        clothing_type: str,
        color: str,
        text_on_garment: str,
        description: str,
    ) -> str:
        """Find catalogue products matching a described garment.

        Scores all 102 catalogue entries locally — no API call, no images — and returns
        the best few as JSON. Call this with what you observed in the customer photo.

        Args:
            clothing_type: Garment category, e.g. hoodie, crewneck, t-shirt, quarter-zip.
            color: Primary colour of the garment, one simple word.
            text_on_garment: Words printed on the garment, verbatim. Empty if none.
            description: One or two sentences describing the garment.
        """
        observation = GarmentObservation(
            garment_present=True,
            clothing_type=tools.coerce_clothing_type(clothing_type),
            color=color,
            text_on_garment=text_on_garment,
            description=description,
        )
        ctx.deps.observation = observation
        ctx.deps.candidates = tools.shortlist_catalogue(observation)

        if not ctx.deps.candidates:
            return "No catalogue product shares any distinctive feature with that garment."
        return tools.summarize_candidates(ctx.deps.candidates)

    @agent.tool
    async def compare_candidate_photos(
        ctx: RunContext[IdentifyDeps], product_ids: list[str]
    ) -> str:
        """View the customer photo alongside candidate product photos in one call.

        Args:
            product_ids: Catalogue product ids to compare, at most 10.
        """
        return await tools.compare_candidate_photos(ctx.deps.image_path, product_ids)

    return agent


def build_ad_agent() -> Agent[AdDeps, AdEffectivenessResult]:
    """The same agent and system prompt, wired for the ad-effectiveness ability."""
    client = tools.make_client()
    model = OpenAIResponsesModel(
        tools.MODEL_NAME, provider=OpenAIProvider(openai_client=client)
    )

    agent = Agent(
        model,
        deps_type=AdDeps,
        output_type=AdEffectivenessResult,
        system_prompt=PROMPT_PATH.read_text(),
        retries=2,
        name="campus-customs-agent",
    )

    @agent.tool
    async def watch_ad(ctx: RunContext[AdDeps]) -> str:
        """Describe the ad video: what happens, how it is shot, its tone, and its call to action.

        Samples frames from the video and analyses them in a single call. You cannot hear
        the soundtrack.
        """
        description = await tools.watch_ad_video(ctx.deps.video_path)
        ctx.deps.frames_sampled = tools.FRAMES_PER_VIDEO
        return description

    @agent.tool
    async def customer_profile(ctx: RunContext[AdDeps]) -> str:
        """Return the customer profile this ad is being judged for."""
        return ctx.deps.profile.model_dump_json(indent=2)

    @agent.tool
    async def score_fit(
        ctx: RunContext[AdDeps],
        production_quality: int,
        thoughtful_voice: int,
        clear_call_to_action: int,
        sound_logic: int,
    ) -> str:
        """Weight your four ad scores by this customer's priorities and return a 0-100 fit.

        Args:
            production_quality: How polished the ad is, 1-5.
            thoughtful_voice: How authentic rather than salesy it sounds, 1-5.
            clear_call_to_action: How clearly it says what to do next, 1-5.
            sound_logic: How well it argues a real reason to buy, 1-5.
        """
        scores = AdQualityScores(
            production_quality=production_quality,
            thoughtful_voice=thoughtful_voice,
            clear_call_to_action=clear_call_to_action,
            sound_logic=sound_logic,
        )
        fit = tools.weighted_fit(scores, ctx.deps.profile)
        ctx.deps.scores = scores
        ctx.deps.fit = fit

        priorities = ctx.deps.profile.ad_priorities
        return json.dumps(
            {
                "weighted_fit": fit,
                "profile_priorities": priorities.model_dump(),
                "note": (
                    "Weighted by this customer's priorities. Report this number as "
                    "weighted_fit rather than estimating your own."
                ),
            },
            indent=2,
        )

    return agent


async def run_with_audit(
    agent: Agent,
    prompt: object,
    deps: object,
    ability: str,
    inputs: dict[str, str],
):
    """Drive the agent loop node by node, appending an audit record per iteration.

    `agent.iter()` rather than `agent.run()` because the audit has to reflect what the
    agent actually did, iteration by iteration, and be written *as it goes*: a run that
    crashes halfway still leaves evidence of how far it got. Reconstructing the trail
    after a successful run would record nothing about the runs that fail.
    """
    run_id = uuid4().hex[:8]
    iteration = 0
    # Tool results arrive on the *next* node, so calls wait here until they can be paired.
    pending: dict[str, AuditEntry] = {}

    def flush(stop_reason: str | None = None) -> None:
        """Append whatever is buffered, optionally marking the end of the run."""
        entries = list(pending.values())
        pending.clear()
        for index, entry in enumerate(entries):
            if stop_reason and index == len(entries) - 1:
                entry.stop_reason = stop_reason
            tools.append_audit(entry)

    async with agent.iter(
        prompt, deps=deps, usage_limits=UsageLimits(request_limit=MAX_ITERATIONS)
    ) as run:
        async for node in run:
            if Agent.is_call_tools_node(node):
                iteration += 1
                parts = node.model_response.parts
                thoughts = " ".join(
                    part.content
                    for part in parts
                    if isinstance(part, (TextPart, ThinkingPart)) and part.content
                )
                calls = [part for part in parts if isinstance(part, ToolCallPart)]

                if not calls:
                    # The model answered instead of calling a tool: that is the last turn.
                    pending[f"final-{iteration}"] = AuditEntry(
                        run_id=run_id,
                        timestamp=datetime.now(timezone.utc),
                        ability=ability,
                        inputs=inputs,
                        iteration=iteration,
                        thoughts=tools.summarize_for_audit(thoughts),
                    )
                for call in calls:
                    pending[call.tool_call_id] = AuditEntry(
                        run_id=run_id,
                        timestamp=datetime.now(timezone.utc),
                        ability=ability,
                        inputs=inputs,
                        iteration=iteration,
                        thoughts=tools.summarize_for_audit(thoughts),
                        tool_name=call.tool_name,
                        tool_args=call.args_as_dict() if call.args else {},
                    )

            elif Agent.is_model_request_node(node):
                # Pair each tool result back to the call that produced it, then write.
                for part in node.request.parts:
                    if isinstance(part, ToolReturnPart) and part.tool_call_id in pending:
                        pending[part.tool_call_id].tool_result_summary = (
                            tools.summarize_for_audit(part.content)
                        )
                flush()

            elif Agent.is_end_node(node):
                flush("final output produced")

    flush("run ended")
    return run.result


async def identify(agent: Agent[IdentifyDeps, IdentifyResult], image_path: Path) -> IdentifyResult:
    """Run the agent against one photo."""
    deps = IdentifyDeps(image_path)
    prompt = [
        f"Does a Campus Customs product appear in this photo? Filename: {image_path.name}",
        BinaryContent(data=image_path.read_bytes(), media_type="image/jpeg"),
    ]

    result = await run_with_audit(
        agent, prompt, deps, "identify", {"image": str(image_path)}
    )
    verdict = result.output

    # Fill in the fields the agent shouldn't be trusted to echo back, and attach the
    # working the tools produced so a wrong verdict can be diagnosed later.
    verdict.image_file = image_path.name
    if verdict.observation is None:
        verdict.observation = deps.observation
    if not verdict.candidates_considered:
        verdict.candidates_considered = deps.candidates
    return verdict


async def judge_ad(video_path: Path, profile_path: Path, out_path: Path) -> int:
    """Judge one ad video against one customer profile."""
    profile = tools.load_profile(profile_path)
    agent = build_ad_agent()
    deps = AdDeps(video_path, profile)

    print(f"→ {video_path.name} judged for {profile.label} ({profile.profile_id})")
    result = await run_with_audit(
        agent,
        f"Judge how effective the ad '{video_path.name}' would be at convincing this "
        f"customer to shop at Campus Customs.",
        deps,
        "ad_effectiveness",
        {"video": str(video_path), "profile": str(profile_path)},
    )
    verdict = result.output

    # Pin the bookkeeping fields to what actually ran, rather than what the model reports.
    verdict.video_file = video_path.name
    verdict.profile_id = profile.profile_id
    verdict.profile_label = profile.label
    verdict.frames_sampled = deps.frames_sampled or tools.FRAMES_PER_VIDEO
    verdict.audio_analyzed = False
    if deps.scores is not None:
        verdict.ad_scores = deps.scores
    if deps.fit is not None:
        verdict.weighted_fit = deps.fit

    scores = verdict.ad_scores
    print(
        f"  scores: production={scores.production_quality} voice={scores.thoughtful_voice} "
        f"cta={scores.clear_call_to_action} logic={scores.sound_logic}"
    )
    print(f"  weighted fit: {verdict.weighted_fit}/100")
    print(f"  likelihood to shop: {verdict.likelihood_to_shop.value}")
    print(f"  {verdict.reasoning}")

    # Keyed by (video, profile) so running each profile separately accumulates both.
    existing: dict[str, AdEffectivenessResult] = {}
    if out_path.exists():
        try:
            previous = AdEffectivenessRun.model_validate_json(out_path.read_text())
            existing = {f"{r.video_file}::{r.profile_id}": r for r in previous.results}
        except Exception:
            pass
    existing[f"{verdict.video_file}::{verdict.profile_id}"] = verdict

    run_record = AdEffectivenessRun(
        generated_at=datetime.now(timezone.utc),
        model=tools.MODEL_NAME,
        results=[existing[k] for k in sorted(existing)],
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(run_record.model_dump_json(indent=2))
    print(f"\nWrote {len(run_record.results)} result(s) to {out_path}")
    return 0


async def run(image_paths: list[Path], out_path: Path) -> int:
    agent = build_agent()
    results: list[IdentifyResult] = []

    for image_path in image_paths:
        print(f"→ {image_path.name}")
        try:
            verdict = await identify(agent, image_path)
        except Exception as exc:  # noqa: BLE001 - one bad photo shouldn't kill the batch
            print(f"  error: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue

        results.append(verdict)
        product = verdict.matched_product_id or "—"
        print(
            f"  product_present={verdict.product_present}  match={product}  "
            f"confidence={verdict.confidence.value}"
        )
        print(f"  {verdict.reasoning}")

    if not results:
        print("No photos were identified successfully.", file=sys.stderr)
        return 1

    # Merge with anything already on disk so identifying one image at a time still
    # builds up the full results file Problem 4 asks for.
    existing: dict[str, IdentifyResult] = {}
    if out_path.exists():
        try:
            previous = IdentifyRun.model_validate_json(out_path.read_text())
            existing = {r.image_file: r for r in previous.results}
        except Exception:
            pass  # a malformed old file shouldn't block a good new run
    existing.update({r.image_file: r for r in results})

    run_record = IdentifyRun(
        generated_at=datetime.now(timezone.utc),
        model=tools.MODEL_NAME,
        results=[existing[k] for k in sorted(existing)],
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(run_record.model_dump_json(indent=2))
    print(f"\nWrote {len(run_record.results)} result(s) to {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Campus Customs agent: identify products in photos, or judge an ad "
        "against a customer profile.",
        epilog=(
            'examples:\n'
            '  python agent.py --image "data/test_images/image_01_true.jpeg"\n'
            '  python agent.py --video "data/videos/ad_humble.mp4" '
            '--profile "profiles/profile_student.json"'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--image",
        nargs="+",
        type=Path,
        help="photo(s) to check for a Campus Customs product",
    )
    parser.add_argument("--video", type=Path, help="ad video to judge")
    parser.add_argument("--profile", type=Path, help="customer profile JSON to judge it for")
    parser.add_argument(
        "--out", type=Path, help="results file (defaults to the one for the chosen ability)"
    )
    args = parser.parse_args()

    if args.image and args.video:
        sys.exit("error: use --image or --video, not both")
    if args.video and not args.profile:
        sys.exit("error: --video also needs --profile (which customer to judge it for)")
    if args.profile and not args.video:
        sys.exit("error: --profile only applies with --video")
    if not args.image and not args.video:
        sys.exit("error: give either --image or --video with --profile")

    required = [p for p in (args.image or []) + [args.video, args.profile] if p is not None]
    missing = [p for p in required if not p.exists()]
    if missing:
        sys.exit("error: no such file: " + ", ".join(str(p) for p in missing))

    if args.video:
        return asyncio.run(judge_ad(args.video, args.profile, args.out or AD_OUTPUT))
    return asyncio.run(run(args.image, args.out or IDENTIFY_OUTPUT))


if __name__ == "__main__":
    sys.exit(main())
