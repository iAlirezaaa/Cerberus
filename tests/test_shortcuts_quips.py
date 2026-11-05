import random
import unittest
from datetime import datetime

from cerberus.quips import LINES, QuipBook, greeting_event, resolve_language
from cerberus.shortcuts import (
    MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, GestureFilter, parse_hotkey,
)


class GestureFilterTests(unittest.TestCase):
    def test_left_then_right_swallows_right_click_completely(self):
        f = GestureFilter("left_right")
        self.assertEqual(f.handle("L_DOWN", 0.0), (False, False))  # app sees left press
        self.assertEqual(f.handle("R_DOWN", 0.1), (True, True))    # chord fires, right hidden
        self.assertEqual(f.handle("R_UP", 0.2), (True, False))     # no right-click menu
        self.assertEqual(f.handle("L_UP", 0.3), (False, False))    # left press completes normally

    def test_right_then_left_swallows_left_and_right_release(self):
        f = GestureFilter("left_right")
        self.assertEqual(f.handle("R_DOWN", 0.0), (False, False))
        self.assertEqual(f.handle("L_DOWN", 0.1), (True, True))
        self.assertEqual(f.handle("L_UP", 0.2), (True, False))
        self.assertEqual(f.handle("R_UP", 0.3), (True, False))

    def test_normal_clicks_pass_through(self):
        f = GestureFilter("left_right")
        for t, event in enumerate(["L_DOWN", "L_UP", "R_DOWN", "R_UP", "M_DOWN", "M_UP"]):
            self.assertEqual(f.handle(event, float(t)), (False, False))

    def test_cooldown_blocks_rapid_refire(self):
        f = GestureFilter("left_right", cooldown=0.6)
        f.handle("L_DOWN", 0.0)
        self.assertTrue(f.handle("R_DOWN", 0.1)[1])
        f.handle("R_UP", 0.15)
        self.assertEqual(f.handle("R_DOWN", 0.2), (True, False))

    def test_other_gestures(self):
        f = GestureFilter("ctrl_middle")
        self.assertEqual(f.handle("M_DOWN", 0.0), (False, False))
        f.handle("M_UP", 0.1)
        self.assertEqual(f.handle("M_DOWN", 1.0, ctrl=True), (True, True))
        self.assertEqual(f.handle("M_UP", 1.1), (True, False))
        back = GestureFilter("back_button")
        self.assertEqual(back.handle("X2_DOWN", 0.0), (False, False))
        self.assertEqual(back.handle("X1_DOWN", 1.0), (True, True))
        self.assertEqual(back.handle("X1_UP", 1.1), (True, False))
        off = GestureFilter("off")
        off.handle("L_DOWN", 0.0)
        self.assertEqual(off.handle("R_DOWN", 0.1), (False, False))


class HotkeyParseTests(unittest.TestCase):
    def test_valid_hotkeys(self):
        self.assertEqual(parse_hotkey("Ctrl+Alt+C"), (MOD_CONTROL | MOD_ALT, ord("C")))
        self.assertEqual(parse_hotkey("Shift+Meta+F5"), (MOD_SHIFT | MOD_WIN, 0x74))
        self.assertEqual(parse_hotkey("F9"), (0, 0x78))
        self.assertEqual(parse_hotkey("Ctrl+Space"), (MOD_CONTROL, 0x20))

    def test_rejects_unsafe_or_invalid(self):
        for text in ("", "C", "Space", "Ctrl+", "Ctrl+Ctrl+C", "Hyper+C", "Ctrl+Ü", "x" * 50):
            with self.subTest(text=text):
                self.assertIsNone(parse_hotkey(text))


class QuipTests(unittest.TestCase):
    def test_every_event_has_both_languages(self):
        for event, languages in LINES.items():
            self.assertTrue(languages.get("en"), event)
            self.assertTrue(languages.get("fa"), event)

    def test_pick_formats_and_avoids_repeats(self):
        book = QuipBook("en", random.Random(3))
        line = book.pick("capture_file", name="report.pdf")
        self.assertIn("report.pdf", line)
        lines = [book.pick("idle") for _ in range(20)]
        self.assertTrue(all(a != b for a, b in zip(lines, lines[1:])))
        self.assertEqual(QuipBook("fa").pick("unknown-event"), "")

    def test_long_names_are_trimmed(self):
        line = QuipBook("en", random.Random(1)).pick("capture_file", name="x" * 200)
        self.assertLess(len(line), 60)

    def test_language_and_greeting(self):
        self.assertEqual(resolve_language("auto", "fa_IR"), "fa")
        self.assertEqual(resolve_language("auto", "en_US"), "en")
        self.assertEqual(resolve_language("fa", "en_US"), "fa")
        self.assertEqual(greeting_event(8), "greet_morning")
        self.assertEqual(greeting_event(23), "greet_night")
        self.assertTrue(QuipBook("fa").greeting(datetime(2026, 1, 1, 14)))


if __name__ == "__main__":
    unittest.main()
