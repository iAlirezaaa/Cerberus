"""Small, bounded manifest reader for transparent PNG / GIF character packs."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import PurePosixPath
from typing import Any

MAX_MANIFEST_BYTES = 256 * 1024
MAX_FRAMES_PER_STATE = 64
MAX_UNIQUE_FRAMES = 400
MAX_FRAME_BYTES = 16 * 1024 * 1024
MAX_DIMENSION = 4096
# Motion phases plus purely visual idle variants the pet rotates through.
IDLE_VARIANTS = ("idle_look", "idle_wag", "idle_wait", "bark")
# Optional idle flourishes (played now and then when present in the pack).
EXTRA_IDLE = ("yawn", "scratch_ear", "chase_tail", "heads_argue")
# Optional clips that stand in for, or bridge between, motion phases.
OPTIONAL_CLIPS = (
    "sit_to_run", "run_to_sit", "turn_around", "held", "petted", "sad", "portal_exit",
    "stash_item", "talk", "think", "sniff", "howl", "peek_in", "celebrate_jump",
    "mini_curl", "mini_wake",
)
ALLOWED_STATES = {
    "idle", "sleep", "wake", "portal", "dash", "catch",
    "celebrate", "play", "alert", "guard", "carry",
    "arrive", "leave", "rouse", "walk", "happy", *IDLE_VARIANTS, *EXTRA_IDLE,
    *OPTIONAL_CLIPS,
}
Box = tuple[int, int, int, int]
IMAGE_SUFFIXES = {".png": "frames", ".gif": "gif"}


@dataclass(frozen=True)
class FrameSequence:
    frames: tuple[str, ...] = ()
    fps: float = 8.0
    loop: bool = False
    gif: str | None = None
    # Looping restarts at this frame (e.g. "fall asleep" then loop the sleeping frames).
    loop_from: int = 0
    # Relative on-screen size; lets packs mix canvases drawn at different zoom levels.
    scale: float = 1.0
    # GIFs use their own frame delays unless fps is set explicitly.
    fps_explicit: bool = True
    # Play the frames backwards (e.g. "fall asleep" reversed = waking up).
    reverse: bool = False
    # Per-frame (x0, y0, x1, y1) box of the carried item, in source pixels,
    # where Cerberus draws an icon of what it actually caught.
    props: tuple[Box | None, ...] = ()
    # PNG lists drawn like GIF clips: cropped and standing on the ground line.
    anchored: bool = False


@dataclass(frozen=True)
class PackManifest:
    default: str
    states: dict[str, FrameSequence]


def _asset_name(value: Any, kind: str = "frames") -> str:
    if not isinstance(value, str) or not value or len(value) > 180:
        raise ValueError("Asset names must be short relative paths")
    if "\\" in value or ":" in value:
        raise ValueError("Asset names must use relative POSIX paths")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("Asset paths must stay inside the animation pack")
    suffix = path.suffix.lower()
    if kind == "default":
        if suffix not in IMAGE_SUFFIXES:
            raise ValueError("The default asset must be a PNG or GIF file")
    elif IMAGE_SUFFIXES.get(suffix) != kind:
        raise ValueError("Frame lists must name PNG files and gif entries GIF files")
    return value


def _props(value: Any, state: str) -> tuple[Box | None, ...]:
    if not isinstance(value, list) or len(value) > MAX_FRAMES_PER_STATE:
        raise ValueError(f"{state} props must be a list of boxes")
    boxes: list[Box | None] = []
    for box in value:
        if box is None:
            boxes.append(None)
            continue
        if (not isinstance(box, list) or len(box) != 4
                or any(type(v) is not int or not 0 <= v <= MAX_DIMENSION for v in box)
                or box[2] <= box[0] or box[3] <= box[1]):
            raise ValueError(f"{state} props entries must be [x0, y0, x1, y1] or null")
        boxes.append((box[0], box[1], box[2], box[3]))
    return tuple(boxes)


def parse_manifest(data: bytes) -> PackManifest:
    """Parse and validate a pack manifest before any image files are read."""
    if not isinstance(data, bytes) or not data or len(data) > MAX_MANIFEST_BYTES:
        raise ValueError("Animation manifest is empty or too large")
    try:
        raw = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Animation manifest must be UTF-8 JSON") from exc
    if (not isinstance(raw, dict) or raw.get("format") != "cerberus-animation-pack"
            or raw.get("version") not in (1, 2)):
        raise ValueError("Unsupported Cerberus animation pack format")
    default = _asset_name(raw.get("default"), "default")
    states_raw = raw.get("states", {})
    if not isinstance(states_raw, dict) or set(states_raw) - ALLOWED_STATES:
        raise ValueError("Animation pack contains an unknown state")
    states: dict[str, FrameSequence] = {}
    asset_names = {default}
    for state, config in states_raw.items():
        if not isinstance(config, dict):
            raise ValueError(f"Invalid {state} frame sequence")
        gif = config.get("gif")
        names = config.get("frames")
        if (gif is None) == (names is None):
            raise ValueError(f"{state} needs exactly one of 'frames' or 'gif'")
        if gif is not None:
            gif = _asset_name(gif, "gif")
            frames: tuple[str, ...] = ()
            asset_names.add(gif)
        else:
            if not isinstance(names, list) or not 1 <= len(names) <= MAX_FRAMES_PER_STATE:
                raise ValueError(f"{state} must contain between 1 and {MAX_FRAMES_PER_STATE} frames")
            frames = tuple(_asset_name(name) for name in names)
            asset_names.update(frames)
        fps_explicit = "fps" in config or gif is None
        fps = config.get("fps", 8)
        loop = config.get("loop", False)
        loop_from = config.get("loop_from", 0)
        scale = config.get("scale", 1.0)
        if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not 0.5 <= fps <= 30:
            raise ValueError(f"{state} fps must be between 0.5 and 30")
        if type(loop) is not bool:
            raise ValueError(f"{state} loop must be a boolean")
        if type(loop_from) is not int or not 0 <= loop_from < MAX_FRAMES_PER_STATE:
            raise ValueError(f"{state} loop_from must be a frame index")
        if frames and loop_from >= len(frames):
            raise ValueError(f"{state} loop_from is past the last frame")
        if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not 0.1 <= scale <= 4:
            raise ValueError(f"{state} scale must be between 0.1 and 4")
        reverse = config.get("reverse", False)
        if type(reverse) is not bool:
            raise ValueError(f"{state} reverse must be a boolean")
        props = _props(config.get("props", []), state)
        if frames and props and len(props) != len(frames):
            raise ValueError(f"{state} props must list one box per frame")
        anchored = config.get("anchored", False)
        if type(anchored) is not bool:
            raise ValueError(f"{state} anchored must be a boolean")
        states[state] = FrameSequence(frames, float(fps), loop, gif, loop_from,
                                      float(scale), fps_explicit, reverse, props,
                                      anchored or gif is not None)
        if len(asset_names) > MAX_UNIQUE_FRAMES:
            raise ValueError(f"An animation pack may use at most {MAX_UNIQUE_FRAMES} unique frames")
    return PackManifest(default, states)
