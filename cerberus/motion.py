"""Deterministic animation state machine, independent of Qt and wall-clock timing."""
from __future__ import annotations

from dataclasses import dataclass, field
import time

# Each short action can be inspected in tests without waiting for timers.
# Durations match one pass of the bundled GIF clips.
DURATIONS = {
    "portal": (1.12, "dash"),
    "dash": (0.80, "catch"),
    "catch": (1.12, "carry"),
    "carry": (1.04, "celebrate"),
    "celebrate": (1.44, "idle"),
    "play": (1.36, "idle"),
    "wake": (1.14, "idle"),
    "alert": (1.12, "idle"),
    "arrive": (1.12, "idle"),
    # Getting up from a nap before running off-screen.
    "rouse": (1.14, "leave"),
}
# "leave" lasts until the widget reports it ran off-screen, "walk" until it reaches
# its spot, "away" until summoned.
OPEN_ENDED = ("idle", "sleep", "guard", "leave", "away", "walk")
# Phases that do not count as the user interacting with the pet.
PASSIVE = ("sleep", "leave", "away", "walk", "rouse")


@dataclass
class MotionMachine:
    """Timeline-based behavior.

    idle -> sleep -> rouse -> leave (runs off-screen) -> away, idle <-> walk, or
    portal -> dash -> catch -> carry -> celebrate after a capture.
    """

    standby_after: float = 95.0
    phase: str = "idle"
    entered_at: float = field(default_factory=time.monotonic)
    last_active_at: float = field(default_factory=time.monotonic)
    reduced_motion: bool = False
    # Seconds without interaction before Cerberus wanders off-screen; None disables it.
    away_after: float | None = None
    # Per-instance copy so the widget can match timings to the clips it loaded.
    durations: dict[str, tuple[float, str]] = field(default_factory=lambda: dict(DURATIONS))

    def set_duration(self, phase: str, seconds: float) -> None:
        """Make a transient phase last exactly as long as its clip (0.3–6 s)."""
        if phase in self.durations:
            self.durations[phase] = (max(0.3, min(6.0, seconds)), self.durations[phase][1])

    def __post_init__(self) -> None:
        if self.standby_after <= 0:
            raise ValueError("standby_after must be positive")
        if self.away_after is not None and self.away_after <= 0:
            raise ValueError("away_after must be positive")

    def transition(self, phase: str, *, now: float | None = None,
                   active: bool | None = None) -> None:
        """Enter a phase; ``active`` says whether it counts as user interaction."""
        if phase not in (*self.durations, *OPEN_ENDED):
            raise ValueError(f"Unknown pet state: {phase}")
        stamp = time.monotonic() if now is None else now
        self.phase = phase
        self.entered_at = stamp
        if (phase not in PASSIVE) if active is None else active:
            self.last_active_at = stamp

    def settle(self, *, now: float | None = None) -> None:
        """Back to idle on its own (e.g. after a stroll) without resetting idle timers."""
        self.transition("idle", now=now, active=False)

    @property
    def is_away(self) -> bool:
        return self.phase in ("leave", "away")

    def capture(self, *, now: float | None = None) -> None:
        self.transition("carry" if self.reduced_motion else "portal", now=now)

    def arrive(self, *, now: float | None = None) -> None:
        """Come back (or come to the cursor) through the Hades portal."""
        self.transition("wake" if self.reduced_motion else "arrive", now=now)

    def dismiss(self, *, now: float | None = None) -> None:
        """The user sent Cerberus away: run off-screen now."""
        self.transition("leave", now=now)

    def touch(self, *, now: float | None = None) -> None:
        stamp = time.monotonic() if now is None else now
        self.transition("wake" if self.phase == "sleep" else "play", now=stamp)

    def update(self, *, now: float | None = None) -> bool:
        """Advance expired transient phases; return True when the state changed."""
        stamp = time.monotonic() if now is None else now
        before = self.phase
        # Bounded transition loop handles resume after a suspended laptop.
        for _ in range(len(self.durations) + 2):
            record = self.durations.get(self.phase)
            if record is None:
                break
            duration, next_phase = record
            if stamp - self.entered_at < duration:
                break
            self.phase = next_phase
            self.entered_at += duration
        idle_for = stamp - self.last_active_at
        if self.phase in ("idle", "sleep") and self.away_after is not None \
                and idle_for >= self.away_after:
            self.phase = "rouse" if self.phase == "sleep" and not self.reduced_motion else "leave"
            self.entered_at = stamp
        elif self.phase == "idle" and idle_for >= self.standby_after:
            self.phase = "sleep"
            self.entered_at = stamp
        return self.phase != before

    def progress(self, *, now: float | None = None) -> float:
        record = self.durations.get(self.phase)
        if record is None:
            return 0.0
        stamp = time.monotonic() if now is None else now
        return max(0.0, min(1.0, (stamp - self.entered_at) / record[0]))
