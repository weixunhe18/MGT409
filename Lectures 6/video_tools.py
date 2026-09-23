"""Local video tools used by the PydanticAI judge."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import imageio.v3 as iio

HERE = Path(__file__).resolve().parent
FRAMES = HERE / "frames"


def sample_frames(video_path: str, every_n_sec: float = 0.5, max_frames: int = 16) -> dict[str, Any]:
    """Sample evenly spaced PNG frames from a clip for visual inspection."""
    path = Path(video_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if every_n_sec <= 0 or max_frames < 1:
        raise ValueError("every_n_sec must be positive and max_frames must be at least 1")

    reader = imageio.get_reader(str(path))
    meta = reader.get_meta_data()
    fps = float(meta.get("fps") or 30.0)
    duration = float(meta.get("duration") or 0.0)
    raw_count = meta.get("nframes")
    estimated_count = (duration * fps) if math.isfinite(duration) else 0
    frame_count = int(raw_count or estimated_count) if math.isfinite(float(raw_count or estimated_count)) else 0
    if frame_count <= 0:
        frame_count = int(reader.count_frames())
    indices = list(range(0, frame_count, max(1, round(every_n_sec * fps))))[:max_frames]

    out_dir = FRAMES / path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for index in indices:
        image = reader.get_data(index)
        output = out_dir / f"frame_{index:06d}.png"
        iio.imwrite(output, image)
        paths.append(output.relative_to(HERE).as_posix())
    reader.close()
    return {"frame_paths": paths, "clip_label": path.name, "fps": fps, "duration_sec": duration}


def describe_video(frame_paths: list[str], clip_label: str) -> dict[str, Any]:
    """Package sampled frames and basic timing for the vision model."""
    return {
        "clip_label": clip_label,
        "frame_paths": frame_paths,
        "play_by_play": "Inspect the attached sampled frames in sequence and describe the action.",
        "sport_guess": "unclear",
        "key_moments": [],
        "notes": "The frame sequence is attached to this tool result for visual review.",
    }


def score_dunk(frame_paths: list[str], description: str, clip_label: str):
    """Return a valid dunk-verdict scaffold for the agent to ground in the frames."""
    from models import DunkVerdict

    return DunkVerdict(
        clip_label=clip_label,
        scores={"height": 0, "creativity": 0, "difficulty": 0, "landing": 0},
        total=0,
        play_by_play=description,
        rationale="Use the sampled frames to replace this scaffold with a grounded assessment.",
        frame_paths=frame_paths,
    )


def call_foul(frame_paths: list[str], description: str, clip_label: str):
    """Return a valid foul-verdict scaffold for the agent to ground in the frames."""
    from models import FoulVerdict

    return FoulVerdict(
        clip_label=clip_label,
        call="no_call",
        confidence=0,
        play_by_play=description,
        rationale="Use the sampled frames to replace this scaffold with a grounded assessment.",
        frame_paths=frame_paths,
    )
