import unittest

from cerberus.motion import MotionMachine


class MotionTests(unittest.TestCase):
    def test_capture_sequence(self):
        m = MotionMachine(standby_after=95)
        m.capture(now=0.0)
        self.assertEqual(m.phase, "portal")
        m.update(now=0.56)
        self.assertEqual(m.phase, "dash")
        m.update(now=1.12)
        self.assertEqual(m.phase, "catch")
        m.update(now=1.79)
        self.assertEqual(m.phase, "celebrate")
        m.update(now=2.50)
        self.assertEqual(m.phase, "celebrate")
        m.update(now=2.60)
        self.assertEqual(m.phase, "idle")

    def test_idle_enters_standby_and_wakes(self):
        m = MotionMachine(standby_after=10, entered_at=0, last_active_at=0)
        self.assertFalse(m.update(now=9))
        self.assertTrue(m.update(now=10))
        self.assertEqual(m.phase, "sleep")
        m.touch(now=12)
        self.assertEqual(m.phase, "wake")
        m.update(now=12.8)
        self.assertEqual(m.phase, "idle")
        m.update(now=20)
        self.assertEqual(m.phase, "idle")
        m.update(now=23)
        self.assertEqual(m.phase, "sleep")

    def test_reduced_motion_skips_portal_and_dash(self):
        m = MotionMachine(reduced_motion=True)
        m.capture(now=10)
        self.assertEqual(m.phase, "catch")
        m.update(now=10.7)
        self.assertEqual(m.phase, "celebrate")

    def test_manual_guard_has_no_idle_timeout(self):
        m = MotionMachine(standby_after=15)
        m.transition("guard", now=0)
        m.update(now=1000)
        self.assertEqual(m.phase, "guard")

    def test_invalid_state_and_timing(self):
        with self.assertRaises(ValueError):
            MotionMachine(standby_after=0)
        m = MotionMachine()
        with self.assertRaises(ValueError):
            m.transition("teleport-out", now=0)


if __name__ == "__main__":
    unittest.main()
