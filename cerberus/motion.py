"""Deterministic animation state machine, independent of Qt and wall-clock timing."""
from __future__ import annotations

from dataclasses import dataclass, field
import time

# Each short action can be inspected in tests without waiting for timers.
DURATIONS = {
    "portal": (0.55, "dash"),
    "dash": (0.55, "catch"),
    "catch": (0.50, "carry"),
    "carry": (0.55, "celebrate"),
    "celebrate": (0.8, "idle"),
    "play": (1.15, "idle"),
    "wake": (0.7, "idle"),
    "alert": (0.9, "idle"),
}


@dataclass
class MotionMachine:
    """Timeline-based behavior: idle -> sleep, or portal -> dash -> catch -> carry -> celebrate."""

    standby_after: float = 95.0
    phase: str = "idle"
    entered_at: float = field(default_factory=time.monotonic)
    last_active_at: float = field(default_factory=time.monotonic)
    reduced_motion: bool = False

    def __post_init__(self) -> None:
        if self.standby_after <= 0:
            raise ValueError("standby_after must be positive")

    def transition(self, phase: str, *, now: float | None = None) -> None:
        if phase not in (*DURATIONS, "idle", "sleep", "guard"):
            raise ValueError(f"Unknown pet state: {phase}")
        stamp = time.monotonic() if now is None else now
        self.phase = phase
        self.entered_at = stamp
        if phase != "sleep":
            self.last_active_at = stamp

    def capture(self, *, now: float | None = None) -> None:
        self.transition("carry" if self.reduced_motion else "portal", now=now)

    def touch(self, *, now: float | None = None) -> None:
        stamp = time.monotonic() if now is None else now
        self.transition("wake" if self.phase == "sleep" else "play", now=stamp)

    def update(self, *, now: float | None = None) -> bool:
        """Advance expired transient phases; return True when the state changed."""
        stamp = time.monotonic() if now is None else now
        before = self.phase
        # Bounded transition loop handles resume after a suspended laptop.
        for _ in range(len(DURATIONS) + 2):
            record = DURATIONS.get(self.phase)
            if record is None:
                break
            duration, next_phase = record
            if stamp - self.entered_at < duration:
                break
            self.phase = next_phase
            self.entered_at += duration
        if self.phase == "idle" and stamp - self.last_active_at >= self.standby_after:
            self.phase = "sleep"
            self.entered_at = stamp
        return self.phase != before

    def progress(self, *, now: float | None = None) -> float:
        record = DURATIONS.get(self.phase)
        if record is None:
            return 0.0
        stamp = time.monotonic() if now is None else now
        return max(0.0, min(1.0, (stamp - self.entered_at) / record[0]))
