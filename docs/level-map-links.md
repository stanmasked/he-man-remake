# Stage 064 — candidate `.lvl` → `.map` resource references

The original iOS level stores metadata for objects of class
`LevelTileMap` and `LevelTileMapOverlay`, and each iOS resource pack
contains independently decoded `.map` files. Stage 064 provides an
**asset-free, read-only local scanner** that checks whether their
identifiers coincide exactly. No substring matching, name guessing or
automatic interpretation of the resulting geometry is allowed.

## What is verified

For one explicitly named `.lvl` (default `MULevel1-1.lvl`), the tool:

- Parses object records from the selected private `screen-med` or
  `screen-xlarge` `levels/` folder.
- Inventories simple `.map` filenames in the same screen pack.
- Looks for **case-sensitive exact name** matches between a map basename
  (with or without its `.map` extension), the object instance name,
  and explicitly typed string properties of `LevelTileMap` or
  `LevelTileMapOverlay` objects.
- Separates objects with no exact candidate, one candidate, or multiple
  **ambiguous** candidates.
- Parses only candidate `.map` files with the existing strict tilemap
  decoder and checks whether they have exactly one layer literally named
  `collision`. It does not invent missing collision layers.

This is an **archive-reference integrity check**, *not* proof that the
original game uses a particular map for a level instance, or that the
`collision` layer's nonempty cells are solid. Unmatched objects are
explicitly recorded, not silently associated. Map geometry, raw tile
IDs, atlas arrays, screenshots and source binaries are not exported.

## Local use, private data only

Run from the repository root with your original archive held locally:

```sh
PYTHONPATH=src python -m heman_tools.level_map_links \
  --ipa /private/He-Man-v2.0.0.ipa \
  --level MULevel1-1.lvl \
  --screen screen-med \
  --out local_reports/level1-map-link-candidates.json

PYTHONPATH=src python -m unittest discover -s tests -v
```

The JSON report contains **source-derived resource names**, so it must
remain private. The CLI enforces the ignored `local_reports/` folder
for output and rejects symlinked roots. No original IPA, `.lvl`,
`.map`, `.shape`, exported statistics or screenshot is ever a CI
fixture. All 19 added unit tests construct their own synthetic binary
maps and synthetic level objects.

## Next independent evidence

To establish a real collision association, combine this metadata with
private object-to-shape ownership checks, calibrated coordinates,
cross-frame and held-out validation, classification of collision
surfaces, and original gameplay traces. The manual review gate described
in `docs/first-level-evidence-gate.md` remains mandatory. The Switch
prototype's synthetic physics is not changed by this stage.
