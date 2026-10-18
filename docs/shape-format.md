# Stage 006 — binary `.shape` geometry

The iOS v2.0.0 IPA contains 409 independently decoded `.shape` entries in `screen-med/geometry`. All corresponding `screen-xlarge/geometry` bytes are identical, so the geometric definitions are resolution-independent in this archive.

## Binary layout (little-endian)

| Field | Encoding | Notes |
|---|---|---|
| Primitive kind | `u32` | `0` = polygon, `1` = circle |
| Flags | `u32` | Observed values 0, 1, 3 and 4; semantics not yet known |
| Name length | `u16` | UTF-16LE code units, 0 when absent |
| Optional name | `UTF-16LE` | References an external map or another named geometry source |
| Polygon vertex count | `u32` | Followed by `count × (float32 x, float32 y)` |
| Circle payload | `float32 × 3` | Radius, center X, center Y |

The polygon payload and circle payload are alternatives. A shape with an external name still has its own geometric primitive. The parser verifies exact end-of-file consumption and finite values.

## Private validation

- 409 / 409 decoded without leftover bytes: **347 polygons and 62 circles**.
- Polygon vertices: **1,496** total; polygons have 3–8 vertices in this version.
- **94** files store an external UTF-16LE reference name.
- All 409 same-named `.shape` pairs match byte-for-byte in the medium- and large-screen asset packs.
- Local regression suite after Stage 006: **63 / 63 synthetic unit tests pass**.
- A level object of class `LevelTileMap` in `MULevel1-1.lvl` points to `MUMap1-1`, and a separate `LevelTileMapOverlay` points to `MUMap1-1.overlay`. Those `.map` resources exist locally, but their body format is not yet decoded.

## What this does *not* establish

The simple local-space shapes alone do not identify which geometry belongs to each rendered level instance or whether a shape is used for solid ground, a hitbox, a sensor, or combat. Do not use these primitives as world collision geometry until their ownership, scaling and coordinate conversion are proven.

`affine_point()` implements the observed 3×3 transformation; it is generic geometry support and not evidence of a particular shape-to-level-object association.

## Run locally (source IPA stays off GitHub)

```sh
PYTHONPATH=src python -m heman_tools.shape_scan \
  --ipa /private/He-Man-v2.0.0.ipa \
  --out local_reports/geometry-shapes.json
PYTHONPATH=src python -m unittest discover -s tests -v
```

No original game binaries, maps, extracted shape files or per-file geometry reports are committed to this public repository.
