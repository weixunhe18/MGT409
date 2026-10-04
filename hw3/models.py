"""Structured data types for the Campus Customs agent.

Every Pydantic model for this homework lives here: the catalogue entry built in
Problem 2, and the identify / ad-effectiveness / profile / audit types added later.
Keeping them in one file means the agent and the build scripts always agree on the
shape of the data they pass around.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ClothingType(str, Enum):
    """Garment categories present in the Campus Customs product line.

    A fixed vocabulary rather than free text: Problem 3 matches a query photo against
    this catalogue, and that only works if "hoodie" is always spelled the same way.
    OTHER is the escape hatch so an unexpected garment doesn't get forced into a
    wrong category.
    """

    T_SHIRT = "t-shirt"
    LONG_SLEEVE = "long-sleeve shirt"
    HOODIE = "hoodie"
    CREWNECK = "crewneck"
    QUARTER_ZIP = "quarter-zip"
    FULL_ZIP = "full-zip"
    JACKET = "jacket"
    FLEECE = "fleece"
    SWEATER = "sweater"
    OTHER = "other"


class CatalogueEntry(BaseModel):
    """One Campus Customs product, derived from its photo.

    Fields fall into two groups: bookkeeping (product_id, image_file) that ties the
    entry back to a file on disk, and observed attributes that the vision model reads
    off the photo.
    """

    product_id: str = Field(
        description="Slug identifying the product, taken from the image filename."
    )
    image_file: str = Field(description="Filename of the source photo in data/products/.")

    clothing_type: ClothingType = Field(description="Garment category.")
    color: str = Field(
        description="Primary color of the garment as a simple word, e.g. navy, grey, white."
    )
    special_note: str = Field(
        description=(
            "Short note on the product's theme: a sport (soccer, hockey), a school or "
            "residential college (Yale, Benjamin Franklin, School of Nursing), or a "
            "family angle (dad, mom, grandpa). 'none' if the garment is unbranded."
        )
    )

    description: str = Field(
        description="One or two sentences describing the garment as it appears in the photo."
    )
    text_on_garment: str = Field(
        default="",
        description=(
            "Words printed on the garment, verbatim. Empty if none. This is the single "
            "strongest signal for matching a query photo to a catalogue product."
        ),
    )


class Confidence(str, Enum):
    """How much weight to put on an identification."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GarmentObservation(BaseModel):
    """What the agent sees in a query photo, before any catalogue lookup happens.

    Deliberately the same vocabulary as CatalogueEntry: the whole matching strategy is
    to describe the query photo in the catalogue's own terms, then compare descriptions
    instead of comparing images pairwise.
    """

    garment_present: bool = Field(
        description="Whether any item of clothing is visible in the photo at all."
    )
    clothing_type: ClothingType = Field(description="Garment category, if one is visible.")
    color: str = Field(description="Primary color of the garment, one simple word.")
    text_on_garment: str = Field(
        default="", description="Words printed on the garment, verbatim. Empty if none."
    )
    description: str = Field(description="One or two sentences on what the photo shows.")


class CandidateMatch(BaseModel):
    """A catalogue product the shortlist step considers plausible."""

    product_id: str
    score: float = Field(description="Local similarity score against the observation.")
    reason: str = Field(description="Which features drove the score.")


class IdentifyResult(BaseModel):
    """The agent's verdict on whether a Campus Customs product appears in a photo.

    `product_present` is the headline answer the test images are graded on; the
    observation and candidate list are kept so a wrong verdict can be diagnosed —
    a bad match and a bad initial reading of the photo need different fixes.
    """

    image_file: str = Field(description="Query photo the verdict applies to.")
    product_present: bool = Field(
        description="True if a Campus Customs catalogue product appears in the photo."
    )
    matched_product_id: str | None = Field(
        default=None,
        description="Catalogue product_id of the match, if one could be identified.",
    )
    confidence: Confidence
    reasoning: str = Field(description="Short explanation of the verdict.")

    observation: GarmentObservation | None = Field(
        default=None, description="What the agent saw before consulting the catalogue."
    )
    candidates_considered: list[CandidateMatch] = Field(
        default_factory=list, description="Shortlisted products, best first."
    )


class IdentifyRun(BaseModel):
    """All identify results written to output/identify_product.json."""

    generated_at: datetime
    model: str
    results: list[IdentifyResult]


class AudienceRole(str, Enum):
    """Who the customer is relative to Yale."""

    STUDENT = "student"
    PARENT = "parent"


class AdPriorities(BaseModel):
    """How much a customer cares about each quality of an ad, from 1 to 5.

    These are weights, not scores: they describe what *this person* responds to, so the
    same ad can legitimately land well with one profile and badly with another. Keeping
    them as explicit numbers means the ad-effectiveness ability in Problem 5 has something
    concrete to reason against instead of guessing at a vibe.
    """

    production_quality: int = Field(
        ge=1, le=5, description="Weight on polish: camera work, editing, sound, styling."
    )
    thoughtful_voice: int = Field(
        ge=1,
        le=5,
        description="Weight on tone — whether the ad sounds authentic rather than salesy.",
    )
    clear_call_to_action: int = Field(
        ge=1, le=5, description="Weight on knowing exactly what to do next, and where."
    )
    sound_logic: int = Field(
        ge=1,
        le=5,
        description="Weight on the argument holding up: real reasons to buy, not just mood.",
    )


class CustomerProfile(BaseModel):
    """A customer the agent judges an ad against.

    Demographics set the scene, but the fields that actually do work are `traits`,
    `ad_priorities`, and `skeptical_of` — an ad "working" means it lands with a specific
    person's taste, so the profile has to say what that taste is rather than just who
    they are.
    """

    profile_id: str = Field(description="Slug identifying the profile, e.g. student.")
    label: str = Field(description="Short human-readable name for the persona.")
    role: AudienceRole

    age_min: int = Field(ge=0, description="Youngest age in the bracket.")
    age_max: int = Field(ge=0, description="Oldest age in the bracket.")
    traits: list[str] = Field(description="Personality traits that shape what appeals.")

    relationship_to_yale: str = Field(description="How this person connects to Yale.")
    buying_motivation: str = Field(
        description="Why this person would buy Campus Customs apparel at all."
    )
    price_sensitivity: str = Field(description="How much cost factors into the decision.")
    skeptical_of: str = Field(
        description="What makes this person tune an ad out — the failure mode to avoid."
    )

    ad_priorities: AdPriorities


class Likelihood(str, Enum):
    """How likely this ad is to actually move this customer to shop."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AdQualityScores(BaseModel):
    """How well the ad performs on each of the four qualities, 1 to 5.

    Deliberately the same four axes as `AdPriorities`, so a score can be multiplied by
    the matching weight. These describe the *ad*; the priorities describe the *person*.
    """

    production_quality: int = Field(ge=1, le=5, description="Polish of the craft.")
    thoughtful_voice: int = Field(ge=1, le=5, description="Authenticity of the tone.")
    clear_call_to_action: int = Field(
        ge=1, le=5, description="How clearly it says what to do next."
    )
    sound_logic: int = Field(ge=1, le=5, description="Whether it gives real reasons to buy.")


class AdEffectivenessResult(BaseModel):
    """The agent's judgement of one ad against one customer profile.

    Scored per-axis rather than as a single number, because "this ad is good" is not a
    useful answer — the point is *which* qualities land with *this* customer, and an ad
    can be excellent and still miss the person it is shown to.
    """

    video_file: str
    profile_id: str
    profile_label: str

    ad_scores: AdQualityScores = Field(description="How the ad rates on each axis.")
    weighted_fit: float = Field(
        ge=0,
        le=100,
        description=(
            "Ad scores weighted by this profile's priorities, 0-100. Computed in code "
            "rather than estimated, so the same ad and profile always give the same number."
        ),
    )
    likelihood_to_shop: Likelihood = Field(
        description="Whether this customer would actually visit Campus Customs after seeing it."
    )

    strengths: list[str] = Field(description="What works for this specific customer.")
    weaknesses: list[str] = Field(description="What fails for this specific customer.")
    reasoning: str = Field(description="Short explanation tying the ad to this profile.")
    recommendation: str = Field(
        description="The single change that would most improve the ad for this customer."
    )

    frames_sampled: int = Field(description="How many video frames the judgement is based on.")
    audio_analyzed: bool = Field(
        default=False,
        description=(
            "Whether the soundtrack was analysed. Currently always false — the transcription "
            "endpoint is not available on this deployment — so voice and music are judged "
            "only from what is visible."
        ),
    )


class AdEffectivenessRun(BaseModel):
    """All ad judgements written to output/ad_effectiveness.json."""

    generated_at: datetime
    model: str
    results: list[AdEffectivenessResult]


class AuditEntry(BaseModel):
    """One iteration of the agent loop, recorded for later audit.

    Written as the run happens rather than reconstructed afterwards, so a run that
    crashes or is interrupted still leaves a record of how far it got. Every appended
    record has this same shape, which is what makes the trail greppable months later.
    """

    run_id: str = Field(description="Groups all iterations belonging to one agent run.")
    timestamp: datetime = Field(description="When this iteration was recorded, UTC.")
    ability: str = Field(description="Which ability ran: identify or ad_effectiveness.")
    inputs: dict[str, str] = Field(
        default_factory=dict,
        description="Files this run was given — which photo, video, or profile.",
    )

    iteration: int = Field(description="1-based position in the agent loop.")
    thoughts: str = Field(
        default="", description="What the model said before acting on this iteration."
    )

    tool_name: str | None = Field(default=None, description="Tool called, if any.")
    tool_args: dict[str, Any] = Field(
        default_factory=dict, description="Arguments the model passed to the tool."
    )
    tool_result_summary: str = Field(
        default="",
        description="Truncated tool output — enough to audit the decision, not a data dump.",
    )

    stop_reason: str | None = Field(
        default=None,
        description="Why the loop ended. Only set on the final entry of a run.",
    )


class CatalogueFailure(BaseModel):
    """A photo that could not be catalogued, and why.

    Recorded rather than silently dropped so the catalogue is auditable: a reader can
    tell the difference between "this product does not exist" and "this product could
    not be processed".
    """

    image_file: str
    reason: str


class Catalogue(BaseModel):
    """The full product catalogue written to output/catalogue.json."""

    generated_at: datetime
    model: str = Field(description="Model ID used to read the photos.")
    entry_count: int
    entries: list[CatalogueEntry]
    failures: list[CatalogueFailure] = Field(
        default_factory=list, description="Photos that could not be catalogued."
    )
