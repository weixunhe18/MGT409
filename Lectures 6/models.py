"""Structured verdicts returned by the sports video judge."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DunkScores(BaseModel):
    height: float = Field(ge=0, le=10)
    creativity: float = Field(ge=0, le=10)
    difficulty: float = Field(ge=0, le=10)
    landing: float = Field(ge=0, le=10)


class DunkVerdict(BaseModel):
    kind: Literal["dunk"] = "dunk"
    clip_label: str
    scores: DunkScores
    total: float = Field(ge=0, le=40)
    play_by_play: str
    rationale: str
    frame_paths: list[str] = Field(default_factory=list)


class FoulVerdict(BaseModel):
    kind: Literal["foul"] = "foul"
    clip_label: str
    call: Literal["foul", "flop", "no_call"]
    confidence: float = Field(ge=0, le=1)
    play_by_play: str
    rationale: str
    frame_paths: list[str] = Field(default_factory=list)
