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

Version 2 manifests may use a GIF instead of a PNG list: `{ "gif": "gifs/run.gif", "loop": true }`. GIF clips use their own frame delays unless `fps` is given, are cropped to the visible character, and stand on a common ground line. Optional `loop_from` (frame index the loop restarts at, e.g. fall asleep then loop the sleeping frames) and `scale` (0.1–4, to match clips drawn at a different zoom) apply to both kinds. Extra state names `arrive`, `leave`, and idle variants `idle_look`, `idle_wag`, `idle_wait`, `bark` are accepted. GIFs must have a transparent background and at most 64 frames.

All paths are relative to the manifest directory, use `/`, stay inside the pack, and name PNG files. The default frame is required. State names are `idle`, `sleep`, `wake`, `portal`, `dash`, `catch`, `carry`, `celebrate`, `play`, `alert`, and `guard`. Each sequence accepts 1–64 frames, 0.5–30 FPS, and a boolean `loop`. A pack may use at most 128 unique frames total. PNG files must include an alpha channel, be no larger than 16 MiB, and stay within 4096×4096 pixels; all decoded frames together are limited to 32 million pixels. Frames within a sequence must use the same canvas dimensions. Invalid or missing optional packs fall back to the bundled SVG. Pack images are preloaded before the animation starts; no file I/O occurs in the paint/timer path. Large images are downscaled to a maximum 768 px render dimension after validation to limit steady-state memory use.

The bundled manifest maps generated transparent poses to running, carrying, sleeping and guard states. These are single-frame state poses animated with lightweight whole-character motion transforms. The pack loader supports authored multi-frame sequences, but a production sprite atlas with independently animated heads, paws and tail has not yet been authored. No claim of 3D rigging or physical Windows validation is made.
