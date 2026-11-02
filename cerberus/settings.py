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

    @classmethod
    def load(cls, home: Path | None = None) -> "Settings":
        path = (home or data_dir()) / "settings.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return cls()
            return cls(**{
                key: raw[key] for key in ("clipboard_capture", "show_pet", "reduced_motion")
                if type(raw.get(key)) is bool
            })
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self, home: Path | None = None) -> None:
        root = home or data_dir()
        root.mkdir(parents=True, exist_ok=True)
        path = root / "settings.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        os.replace(tmp, path)
