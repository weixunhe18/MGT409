#!/usr/bin/env python3
"""Build short, seamless product loops from the flat catalogue photos.

    .venv/bin/python scripts/make_motion_loops.py

What this does and does not do
------------------------------
This is the *Standard Tier* of the brief: subtle camera parallax generated from a
2D still. It is a slow push-in toward a focal point on the garment, rendered
forward and then reversed so the loop is seamless with no cut.

It does **not** produce the Top Tier footage (a model walking across campus) or
AI-generated fabric movement — both need source material or a video model that is
not available here. Swapping in real footage later means dropping files with the
same names into data/motion/; nothing in the frontend changes.

Output per product, meeting the asset spec:
  * WebM (VP9) primary + MP4 (H.264) fallback for Safari
  * 1080x1080, 30 fps, ~2.5 s, seamless loop
  * no audio track at all (required for autoplay)
  * target <= 1.5 MB per clip
"""

import json
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

HW_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = HW_DIR / "data" / "products"
OUT_DIR = HW_DIR / "data" / "motion"

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

SIZE = 1080
FPS = 30
FWD_FRAMES = 38  # forward half; ping-pong makes the clip ~2.5 s
ZOOM = 0.14  # how far the camera pushes in over the forward half
MAX_BYTES = 1_500_000

# focal_x / focal_y are 0..1 across the frame — where the push-in heads for.
HEROES = [
    {
        "product_id": "benjamin-franklin-1-4-zip",
        "preset": "Details & Spin",
        "caption": "Push-in on the Benjamin Franklin crest",
        "focal_x": 0.58,
        "focal_y": 0.40,
    },
    {
        "product_id": "2025-yale-vs-harvard-t-shirt",
        "preset": "Details & Spin",
        "caption": "Push-in on The Game graphic",
        "focal_x": 0.50,
        "focal_y": 0.46,
    },
    {
        "product_id": "champion-reverse-weave-hoodie-1",
        "preset": "Walk & Flare",
        "caption": "Slow drift across the hood and chest",
        "focal_x": 0.50,
        "focal_y": 0.34,
    },
]


def build_filter(focal_x: float, focal_y: float) -> str:
    """Forward push-in, then the same frames reversed, concatenated.

    The reversed half is trimmed at both ends: without that, the last forward
    frame repeats at the turn and the first frame repeats at the loop point,
    which reads as a stutter twice per cycle.
    """
    work = int(SIZE * 1.3)  # headroom so cropping never samples past the edge
    duration = FWD_FRAMES / FPS
    # Crop window shrinks from the full frame to 1/(1+ZOOM) of it.
    zz = f"(1+{ZOOM}*min(t/{duration:.5f},1))"
    cw = f"(iw/{zz})"
    ch = f"(ih/{zz})"
    # Pan so the shrinking window drifts toward the focal point.
    cx = f"(iw-{cw})*{focal_x:.3f}"
    cy = f"(ih-{ch})*{focal_y:.3f}"

    return (
        f"[0:v]scale={work}:{work}:flags=lanczos,"
        f"crop=w='{cw}':h='{ch}':x='{cx}':y='{cy}',"
        f"scale={SIZE}:{SIZE}:flags=lanczos,fps={FPS},"
        f"setsar=1,format=yuv420p,setpts=PTS-STARTPTS[fwd];"
        f"[fwd]split[f1][f2];"
        f"[f2]reverse,trim=start_frame=1:end_frame={FWD_FRAMES - 1},"
        f"setpts=PTS-STARTPTS[rev];"
        f"[f1][rev]concat=n=2:v=1[out]"
    )


def encode(src: Path, dest: Path, hero: dict, codec: str) -> None:
    vf = build_filter(hero["focal_x"], hero["focal_y"])
    duration = FWD_FRAMES / FPS

    if codec == "webm":
        codec_args = [
            "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "36",
            "-row-mt", "1", "-deadline", "good", "-cpu-used", "2",
        ]
    else:
        codec_args = [
            "-c:v", "libx264", "-crf", "25", "-preset", "slow",
            "-profile:v", "high", "-movflags", "+faststart",
        ]

    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-t", f"{duration:.5f}", "-i", str(src),
        "-filter_complex", vf, "-map", "[out]",
        "-an",  # strip audio entirely; required for autoplay
        "-pix_fmt", "yuv420p",
        *codec_args,
        str(dest),
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    failed = False

    for hero in HEROES:
        pid = hero["product_id"]
        src = SRC_DIR / f"{pid}.jpg"
        if not src.exists():
            print(f"!! missing source {src}")
            failed = True
            continue

        sizes = {}
        for codec, ext in (("webm", "webm"), ("mp4", "mp4")):
            dest = OUT_DIR / f"{pid}.{ext}"
            print(f"  encoding {dest.name} …", flush=True)
            encode(src, dest, hero, codec)
            size = dest.stat().st_size
            sizes[ext] = size
            flag = "OK " if size <= MAX_BYTES else "OVER BUDGET"
            print(f"    {size/1024:8.1f} KB  {flag}")
            if size > MAX_BYTES:
                failed = True

        manifest[pid] = {
            "preset": hero["preset"],
            "caption": hero["caption"],
            "webm": f"/motion/{pid}.webm",
            "mp4": f"/motion/{pid}.mp4",
            "bytes": sizes,
        }

    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\nwrote {OUT_DIR / 'manifest.json'} with {len(manifest)} entries")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
