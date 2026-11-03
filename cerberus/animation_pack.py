"""Small, bounded manifest reader for transparent PNG character packs."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import PurePosixPath
from typing import Any

MAX_MANIFEST_BYTES = 256 * 1024
MAX_FRAMES_PER_STATE = 64
MAX_UNIQUE_FRAMES = 128
MAX_FRAME_BYTES = 16 * 1024 * 1024
MAX_DIMENSION = 4096
ALLOWED_STATES = {
    "idle", "sleep", "wake", "portal", "dash", "catch",
    "celebrate", "play", "alert", "guard",
}


@dataclass(frozen=True)
class FrameSequence:
    frames: tuple[str, ...]
    fps: float = 8.0
    loop: bool = False


@dataclass(frozen=True)
class PackManifest:
    default: str
    states: dict[str, FrameSequence]


def _asset_name(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 180:
        raise ValueError("Asset names must be short relative paths")
    if "\\" in value or ":" in value:
        raise ValueError("Asset names must use relative POSIX paths")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("Asset paths must stay inside the animation pack")
    if path.suffix.lower() != ".png":
        raise ValueError("Animation assets must be PNG files")
    return value


def parse_manifest(data: bytes) -> PackManifest:
    """Parse and validate a v1 pack manifest before any image files are read."""
    if not isinstance(data, bytes) or not data or len(data) > MAX_MANIFEST_BYTES:
        raise ValueError("Animation manifest is empty or too large")
    try:
        raw = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Animation manifest must be UTF-8 JSON") from exc
    if not isinstance(raw, dict) or raw.get("format") != "cerberus-animation-pack" or raw.get("version") != 1:
        raise ValueError("Unsupported Cerberus animation pack format")
    default = _asset_name(raw.get("default"))
    states_raw = raw.get("states", {})
    if not isinstance(states_raw, dict) or set(states_raw) - ALLOWED_STATES:
        raise ValueError("Animation pack contains an unknown state")
    states: dict[str, FrameSequence] = {}
    asset_names = {default}
    for state, config in states_raw.items():
        if not isinstance(config, dict):
            raise ValueError(f"Invalid {state} frame sequence")
        names = config.get("frames")
        if not isinstance(names, list) or not 1 <= len(names) <= MAX_FRAMES_PER_STATE:
            raise ValueError(f"{state} must contain between 1 and {MAX_FRAMES_PER_STATE} frames")
        fps = config.get("fps", 8)
        loop = config.get("loop", False)
        if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not 0.5 <= fps <= 30:
            raise ValueError(f"{state} fps must be between 0.5 and 30")
        if type(loop) is not bool:
            raise ValueError(f"{state} loop must be a boolean")
        states[state] = FrameSequence(tuple(_asset_name(name) for name in names), float(fps), loop)
        asset_names.update(names)
        if len(asset_names) > MAX_UNIQUE_FRAMES:
            raise ValueError(f"An animation pack may use at most {MAX_UNIQUE_FRAMES} unique frames")
    return PackManifest(default, states)
