import json
import unittest

from cerberus.animation_pack import parse_manifest


def manifest(**changes):
    value = {
        "format": "cerberus-animation-pack",
        "version": 1,
        "default": "guardian.png",
        "states": {},
    }
    value.update(changes)
    return json.dumps(value).encode("utf-8")


class AnimationPackTests(unittest.TestCase):
    def test_reads_default_and_timed_state_frames(self):
        parsed = parse_manifest(manifest(states={
            "idle": {"frames": ["idle/000.png", "idle/001.png"], "fps": 3, "loop": True},
            "catch": {"frames": ["catch.png"]},
        }))
        self.assertEqual(parsed.default, "guardian.png")
        self.assertEqual(parsed.states["idle"].frames, ("idle/000.png", "idle/001.png"))
        self.assertEqual(parsed.states["idle"].fps, 3.0)
        self.assertTrue(parsed.states["idle"].loop)
        self.assertFalse(parsed.states["catch"].loop)

    def test_rejects_paths_outside_pack(self):
        with self.assertRaises(ValueError):
            parse_manifest(manifest(default="../outside.png"))
        with self.assertRaises(ValueError):
            parse_manifest(manifest(states={"idle": {"frames": ["..\\outside.png"]}}))

    def test_rejects_unbounded_or_unknown_sequences(self):
        with self.assertRaises(ValueError):
            parse_manifest(manifest(states={"idle": {"frames": ["a.png"], "fps": 31}}))
        with self.assertRaises(ValueError):
            parse_manifest(manifest(states={"surprise": {"frames": ["a.png"]}}))
        with self.assertRaises(ValueError):
            parse_manifest(manifest(states={"idle": {"frames": ["a.png"] * 65}}))

    def test_rejects_too_many_unique_frames_across_states(self):
        with self.assertRaises(ValueError):
            parse_manifest(manifest(states={
                "idle": {"frames": [f"idle/{index}.png" for index in range(64)]},
                "sleep": {"frames": [f"sleep/{index}.png" for index in range(64)]},
                "wake": {"frames": ["wake.png"]},
            }))


if __name__ == "__main__":
    unittest.main()
