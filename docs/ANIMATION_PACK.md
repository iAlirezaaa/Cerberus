# Cerberus PNG animation packs

Cerberus can load local PNG frame sequences without changing the capture or vault code. The bundled pack lives in `cerberus/assets/animation-pack.json`; set `CERBERUS_ASSET_PACK` to another manifest file to load a custom pack.

```json
{
  "format": "cerberus-animation-pack",
  "version": 1,
  "default": "guardian.png",
  "states": {
    "idle": { "frames": ["idle/000.png", "idle/001.png"], "fps": 2, "loop": true },
    "catch": { "frames": ["catch/000.png", "catch/001.png"], "fps": 12, "loop": false }
  }
}
```

All paths are relative to the manifest directory, use `/`, stay inside the pack, and name PNG files. The default frame is required. State names are `idle`, `sleep`, `wake`, `portal`, `dash`, `catch`, `celebrate`, `play`, `alert`, and `guard`. Each sequence accepts 1–64 frames, 0.5–30 FPS, and a boolean `loop`. A pack may use at most 128 unique frames total. PNG files must include an alpha channel, be no larger than 16 MiB, and stay within 4096×4096 pixels; all decoded frames together are limited to 32 million pixels. Frames within a sequence must use the same canvas dimensions. Invalid or missing optional packs fall back to the bundled SVG. Pack images are preloaded before the animation starts; no file I/O occurs in the paint/timer path.

The bundled `guardian-ember.png` is a single generated transparent pose. It is animated using the existing lightweight whole-character motion transforms. The pack loader supports authored per-state frame sequences, but a production sprite atlas with independently animated heads, paws and tail has not yet been authored. No claim of 3D rigging or physical Windows validation is made.
