# Round 4 item: `scratch_ear`

You are making ONE item for the Cerberus desktop pet. **The attached images are the exact,
approved character.** Pass these attached images to your image-generation tool as reference
images for the generation, and keep the design identical: same three wolf heads with glowing
diamond runes, charcoal-brown fur with glowing orange lava cracks, amber eyes, bronze Greek-key
collar with the round Ψ trident medallion, flame-tipped tail, chunky cute proportions, same
lighting and colours. **Facing RIGHT** like the references (unless told otherwise below).

## What to make
8 frames, not looping. Sitting; lifts a back paw and scratches behind an ear, happy squint, then puts the paw down.

## Hard rules
1. Exactly one new image-generation call for the sheet (a second attempt is allowed only if the
   first fails the identity check below). Never reuse, shift, scale, flip or cycle existing pixels,
   and never draw the character or icons with code.
2. Ask for the poses in a single horizontal row with wide empty gutters on a transparent or flat
   background.
3. Save the generated sheet unchanged as `art/codex/sheets/scratch_ear_sheet.png` and add to
   `art/codex/provenance.json` (keep existing entries):
   `"scratch_ear": {"generated_file": "<full path under C:\\Users\\Raven\\.codex\\generated_images>", "prompt": "<prompt>"}`.
4. Identity check before slicing: compare your sheet with the attached references. If it is not
   clearly the same character (e.g. a lean realistic wolf, wrong colours, no collar/medallion,
   facing the wrong way), regenerate once; if still wrong, mark it skipped and stop.
5. **Do not slice or post-process.** The reviewer removes the background and slices the sheet with
   the project's own tool. A plain light background (even a checkerboard) is fine; keep the poses
   well separated and the whole character inside the image.
6. Record the item in `art/codex/manifest.json` as `"sheet_ready"` (or `"skipped"` with the reason).
7. Do not edit `scripts/` or anything outside `art/codex/`. If image generation fails or hits a
   limit, stop and say so. End with one honest paragraph: what you generated and any problems.
