"""Summon shortcuts: mouse gestures and a user-chosen keyboard hotkey.

This module is Qt-free so the decision logic can be unit tested. The Windows
hooks that feed it live in ``cerberus.win_input``. Only button presses relevant
to the chosen gesture are examined; nothing is logged or stored.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MOUSE_GESTURES: dict[str, str] = {
    "left_right": "Left + Right click together",
    "ctrl_middle": "Ctrl + Middle click",
    "back_button": "Mouse side button (Back)",
    "forward_button": "Mouse side button (Forward)",
    "off": "Off",
}
SHORTCUT_ACTIONS: dict[str, str] = {
    "summon": "Bring Cerberus to the cursor",
    "toggle": "Toggle: bring back / send away",
}
DEFAULT_HOTKEY = "Ctrl+Alt+C"

# Windows RegisterHotKey modifier flags.
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
_MODIFIERS = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT,
              "shift": MOD_SHIFT, "meta": MOD_WIN, "win": MOD_WIN}
_NAMED_KEYS = {
    "space": 0x20, "pgup": 0x21, "pgdown": 0x22, "end": 0x23, "home": 0x24,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28, "ins": 0x2D,
    "insert": 0x2D, "del": 0x2E, "delete": 0x2E, "backspace": 0x08, "tab": 0x09,
    "return": 0x0D, "enter": 0x0D, "esc": 0x1B, "escape": 0x1B, "pause": 0x13,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, ";": 0xBA,
    "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF, "\\": 0xDC,
}


def parse_hotkey(text: str) -> tuple[int, int] | None:
    """'Ctrl+Alt+C' -> (modifier flags, virtual-key code); None if empty or invalid.

    Plain keys without a modifier are rejected (except F-keys) so a hotkey can
    never swallow ordinary typing.
    """
    if not isinstance(text, str) or not text.strip() or len(text) > 40:
        return None
    compact = text.replace(" ", "")
    if compact.endswith("++"):
        parts = compact[:-2].split("+") + ["+"]
    else:
        parts = compact.split("+")
    if not parts or any(not part for part in parts):
        return None
    *mods, key = parts
    flags = 0
    for mod in mods:
        flag = _MODIFIERS.get(mod.lower())
        if flag is None or flags & flag:
            return None
        flags |= flag
    lower = key.lower()
    if len(key) == 1 and key.isascii() and key.isalnum():
        vk = ord(key.upper())
    elif lower.startswith("f") and lower[1:].isdigit() and 1 <= int(lower[1:]) <= 24:
        vk = 0x70 + int(lower[1:]) - 1
    elif lower in _NAMED_KEYS:
        vk = _NAMED_KEYS[lower]
    elif key == "+":
        vk = 0xBB
    else:
        return None
    if not flags and not 0x70 <= vk <= 0x87:
        return None
    return flags, vk


@dataclass
class GestureFilter:
    """Decides, per mouse event, whether to swallow it and whether the gesture fired.

    Events are 'L_DOWN', 'L_UP', 'R_DOWN', 'R_UP', 'M_DOWN', 'M_UP',
    'X1_DOWN', 'X1_UP', 'X2_DOWN', 'X2_UP'. For left+right, whichever button
    completes the chord is swallowed together with the pending right-button
    release, so no application opens its right-click menu.
    """

    mode: str = "left_right"
    cooldown: float = 0.6
    _down: set = field(default_factory=set)
    _swallow_up: set = field(default_factory=set)
    _last_fired: float = float("-inf")

    def _fire(self, now: float) -> bool:
        if now - self._last_fired < self.cooldown:
            return False
        self._last_fired = now
        return True

    def handle(self, event: str, now: float, *, ctrl: bool = False) -> tuple[bool, bool]:
        button, _, edge = event.partition("_")
        if edge == "UP":
            self._down.discard(button)
            if button in self._swallow_up:
                self._swallow_up.discard(button)
                return True, False
            return False, False
        if edge != "DOWN":
            return False, False
        mode = self.mode
        if mode == "left_right" and button in ("L", "R"):
            other = "R" if button == "L" else "L"
            if other in self._down:
                fired = self._fire(now)
                # Swallow this press, its release, and the right button's release.
                self._swallow_up.update({button, "R"})
                self._down.add(button)
                return True, fired
            self._down.add(button)
            return False, False
        if mode == "ctrl_middle" and button == "M" and ctrl:
            self._swallow_up.add("M")
            return True, self._fire(now)
        if (mode, button) in (("back_button", "X1"), ("forward_button", "X2")):
            self._swallow_up.add(button)
            return True, self._fire(now)
        self._down.add(button)
        return False, False


@dataclass
class ChordEdge:
    """Polling fallback for left+right (cannot suppress the click)."""

    cooldown: float = 0.8
    _was_down: bool = False
    _last_fired: float = float("-inf")

    def feed(self, left: bool, right: bool, now: float) -> bool:
        both = bool(left and right)
        fired = both and not self._was_down and now - self._last_fired >= self.cooldown
        self._was_down = both
        if fired:
            self._last_fired = now
        return fired
