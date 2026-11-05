import unittest

from cerberus.shortcuts import ChordEdge
from cerberus.motion import DURATIONS, MotionMachine


class MotionTests(unittest.TestCase):
    def test_capture_sequence(self):
        m = MotionMachine(standby_after=95)
        m.capture(now=0.0)
        self.assertEqual(m.phase, "portal")
        t = 0.0
        for phase in ("portal", "dash", "catch", "carry", "celebrate"):
            duration, next_phase = DURATIONS[phase]
            m.update(now=t + duration - 0.01)
            self.assertEqual(m.phase, phase)
            t += duration
            m.update(now=t + 0.001)
            self.assertEqual(m.phase, next_phase)
        self.assertEqual(m.phase, "idle")

    def test_idle_enters_standby_and_wakes(self):
        m = MotionMachine(standby_after=10, entered_at=0, last_active_at=0)
        self.assertFalse(m.update(now=9))
        self.assertTrue(m.update(now=10))
        self.assertEqual(m.phase, "sleep")
        m.touch(now=12)
        self.assertEqual(m.phase, "wake")
        m.update(now=12 + DURATIONS["wake"][0] + 0.01)
        self.assertEqual(m.phase, "idle")
        m.update(now=20)
        self.assertEqual(m.phase, "idle")
        m.update(now=23)
        self.assertEqual(m.phase, "sleep")

    def test_reduced_motion_skips_portal_and_dash(self):
        m = MotionMachine(reduced_motion=True)
        m.capture(now=10)
        self.assertEqual(m.phase, "carry")
        m.update(now=10 + DURATIONS["carry"][0] + 0.01)
        self.assertEqual(m.phase, "celebrate")

    def test_manual_guard_has_no_idle_timeout(self):
        m = MotionMachine(standby_after=15, away_after=30)
        m.transition("guard", now=0)
        m.update(now=1000)
        self.assertEqual(m.phase, "guard")

    def test_wanders_off_after_sleeping_and_returns(self):
        m = MotionMachine(standby_after=10, away_after=40, entered_at=0, last_active_at=0)
        m.update(now=11)
        self.assertEqual(m.phase, "sleep")
        m.update(now=39)
        self.assertEqual(m.phase, "sleep")
        m.update(now=40)
        # It gets up from the nap first, then runs.
        self.assertEqual(m.phase, "rouse")
        m.update(now=40 + DURATIONS["rouse"][0] + 0.01)
        self.assertEqual(m.phase, "leave")
        self.assertTrue(m.is_away)
        # Leaving is open-ended until the widget reports it is off-screen.
        m.update(now=500)
        self.assertEqual(m.phase, "leave")
        m.transition("away", now=501)
        m.update(now=5000)
        self.assertEqual(m.phase, "away")
        m.arrive(now=6000)
        self.assertEqual(m.phase, "arrive")
        self.assertFalse(m.is_away)
        m.update(now=6000 + DURATIONS["arrive"][0] + 0.01)
        self.assertEqual(m.phase, "idle")
        # Arriving counts as activity, so it will not immediately leave again.
        m.update(now=6020)
        self.assertEqual(m.phase, "sleep")

    def test_walk_and_settle_do_not_count_as_activity(self):
        m = MotionMachine(standby_after=10, away_after=100, entered_at=0, last_active_at=0)
        m.transition("walk", now=5)
        self.assertEqual(m.last_active_at, 0)
        m.settle(now=8)
        self.assertEqual(m.phase, "idle")
        m.update(now=10)
        self.assertEqual(m.phase, "sleep")

    def test_dismiss_leaves_immediately(self):
        m = MotionMachine()
        m.dismiss(now=3)
        self.assertEqual(m.phase, "leave")
        self.assertTrue(m.is_away)

    def test_wander_off_disabled_by_default(self):
        m = MotionMachine(standby_after=10, entered_at=0, last_active_at=0)
        m.update(now=100000)
        self.assertEqual(m.phase, "sleep")

    def test_reduced_motion_arrive_skips_portal(self):
        m = MotionMachine(reduced_motion=True)
        m.transition("away", now=0)
        m.arrive(now=1)
        self.assertEqual(m.phase, "wake")

    def test_invalid_state_and_timing(self):
        with self.assertRaises(ValueError):
            MotionMachine(standby_after=0)
        with self.assertRaises(ValueError):
            MotionMachine(away_after=0)
        m = MotionMachine()
        with self.assertRaises(ValueError):
            m.transition("teleport-out", now=0)


class ChordTests(unittest.TestCase):
    def test_fires_once_per_press_with_cooldown(self):
        chord = ChordEdge(cooldown=0.8)
        self.assertFalse(chord.feed(True, False, 0.0))
        self.assertTrue(chord.feed(True, True, 0.05))
        self.assertFalse(chord.feed(True, True, 0.10))  # still held
        self.assertFalse(chord.feed(False, False, 0.20))
        self.assertFalse(chord.feed(True, True, 0.30))  # within cooldown
        self.assertFalse(chord.feed(False, False, 1.0))
        self.assertTrue(chord.feed(True, True, 1.2))

    def test_single_buttons_never_fire(self):
        chord = ChordEdge()
        for t, (left, right) in enumerate([(True, False), (False, True), (False, False)] * 5):
            self.assertFalse(chord.feed(left, right, float(t)))


if __name__ == "__main__":
    unittest.main()
