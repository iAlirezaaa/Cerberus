"""Local user preferences. No telemetry or cloud configuration."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .shortcuts import DEFAULT_HOTKEY, MOUSE_GESTURES, SHORTCUT_ACTIONS, parse_hotkey

CHAT_LEVELS = ("off", "quiet", "normal", "chatty")
LANGUAGE_CHOICES = ("auto", "en", "fa")


def data_dir() -> Path:
    """Where settings.json lives (and the vault, unless storage_dir moves it)."""
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
    # Run off-screen after this long without interaction.
    wander_off: bool = True
    away_seconds: int = 180
    # Summon shortcuts (see cerberus/shortcuts.py).
    mouse_gesture: str = "left_right"
    hotkey: str = DEFAULT_HOTKEY
    shortcut_action: str = "summon"
    show_return_button: bool = True
    # Liveliness.
    roam: bool = True
    chat_level: str = "normal"
    language: str = "auto"
    # Empty = keep memories next to settings.json in data_dir().
    storage_dir: str = ""

    @classmethod
    def load(cls, home: Path | None = None) -> "Settings":
        path = (home or data_dir()) / "settings.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return cls()
        if not isinstance(raw, dict):
            return cls()
        values: dict[str, object] = {}
        for item in fields(cls):
            if item.type == "bool" and type(raw.get(item.name)) is bool:
                values[item.name] = raw[item.name]
        ranges = {"pet_size": (180, 500), "standby_seconds": (15, 3600),
                  "away_seconds": (30, 7200)}
        for key, (low, high) in ranges.items():
            if type(raw.get(key)) is int and low <= raw[key] <= high:
                values[key] = raw[key]
        choices = {"mouse_gesture": MOUSE_GESTURES, "shortcut_action": SHORTCUT_ACTIONS,
                   "chat_level": CHAT_LEVELS, "language": LANGUAGE_CHOICES}
        for key, allowed in choices.items():
            if raw.get(key) in allowed:
                values[key] = raw[key]
        hotkey = raw.get("hotkey")
        if isinstance(hotkey, str) and (hotkey == "" or parse_hotkey(hotkey)):
            values["hotkey"] = hotkey
        storage = raw.get("storage_dir")
        if isinstance(storage, str) and len(storage) < 1024 and (
                storage == "" or Path(storage).is_absolute()):
            values["storage_dir"] = storage
        # Older settings files stored the left+right toggle as summon_chord.
        if "mouse_gesture" not in values and raw.get("summon_chord") is False:
            values["mouse_gesture"] = "off"
        return cls(**values)

    def save(self, home: Path | None = None) -> None:
        root = home or data_dir()
        root.mkdir(parents=True, exist_ok=True)
        path = root / "settings.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)


def vault_dir(home: Path | None = None, settings: Settings | None = None) -> Path:
    """Folder that holds vault.sqlite3 and files/ (honours the storage_dir setting)."""
    root = home or data_dir()
    current = settings or Settings.load(root)
    return Path(current.storage_dir) if current.storage_dir else root
