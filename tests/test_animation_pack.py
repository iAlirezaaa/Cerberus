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

    def test_reads_gif_states_with_loop_from_and_scale(self):
        parsed = parse_manifest(manifest(version=2, default="gifs/idle.gif", states={
            "sleep": {"gif": "gifs/sleep.gif", "loop": True, "loop_from": 4},
            "idle_wag": {"gif": "gifs/wag.gif", "scale": 0.72},
        }))
        self.assertEqual(parsed.default, "gifs/idle.gif")
        sleep = parsed.states["sleep"]
        self.assertEqual((sleep.gif, sleep.loop_from, sleep.frames), ("gifs/sleep.gif", 4, ()))
        self.assertFalse(sleep.fps_explicit)
        self.assertEqual(parsed.states["idle_wag"].scale, 0.72)

    def test_rejects_bad_gif_entries(self):
        for state in (
            {"gif": "a.png"},
            {"frames": ["a.gif"]},
            {"gif": "a.gif", "frames": ["a.png"]},
            {"gif": "../a.gif"},
            {"gif": "a.gif", "scale": 9},
            {"gif": "a.gif", "loop_from": -1},
            {"frames": ["a.png"], "loop_from": 1},
        ):
            with self.subTest(state=state), self.assertRaises(ValueError):
                parse_manifest(manifest(states={"idle": state}))

    def test_bundled_pack_is_valid_and_complete(self):
        from importlib import resources
        root = resources.files("cerberus").joinpath("assets")
        parsed = parse_manifest(root.joinpath("animation-pack.json").read_bytes())
        for state in ("idle", "sleep", "wake", "portal", "dash", "catch", "carry",
                      "celebrate", "play", "alert", "guard", "arrive", "leave"):
            self.assertIn(state, parsed.states)
            self.assertTrue(root.joinpath(*parsed.states[state].gif.split("/")).is_file())


if __name__ == "__main__":
    unittest.main()
