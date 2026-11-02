"""Local user preferences. No telemetry or cloud configuration."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("CERBERUS_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Cerberus"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Cerberus"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "cerberus"


@dataclass
class Settings:
    clipboard_capture: bool = False
    show_pet: bool = True
    reduced_motion: bool = False
    pet_size: int = 340
    standby_seconds: int = 95

    @classmethod
    def load(cls, home: Path | None = None) -> "Settings":
        path = (home or data_dir()) / "settings.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return cls()
            values = {
                key: raw[key]
                for key in ("clipboard_capture", "show_pet", "reduced_motion")
                if type(raw.get(key)) is bool
            }
            if type(raw.get("pet_size")) is int and 180 <= raw["pet_size"] <= 500:
                values["pet_size"] = raw["pet_size"]
            if type(raw.get("standby_seconds")) is int and 15 <= raw["standby_seconds"] <= 3600:
                values["standby_seconds"] = raw["standby_seconds"]
            return cls(**values)
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self, home: Path | None = None) -> None:
        root = home or data_dir()
        root.mkdir(parents=True, exist_ok=True)
        path = root / "settings.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        os.replace(tmp, path)
