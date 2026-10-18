# Stage 007 — multilayer `.map` tile data

## Data obtained privately

All claims here were checked against the user's local iOS v2.0.0 IPA. Source map bytes and outputs are **not** included in public GitHub.

The normal `.map` format begins with little-endian `u32 layer_count` (observed 1, 2, or 3). Each layer independently serializes:

| Component | Encoding |
|---|---|
| Layer identifier | `u32`, observed zero |
| Visibility | `u8`, 0 or 1 |
| Opacity | `f32`, 0 through 1 |
| Name | `u16` length followed by UTF-16LE |
| Tile and atlas dimensions | four `u32` values |
| Grid width, height, atlas count | three `u32` values |
| Atlas names | `atlas_count` length-prefixed UTF-16LE strings |
| Tile index grid | `width × height` contiguous little-endian `u16` values |
| Atlas index grid | `width × height` contiguous `u8` values |

An empty tile has ID `0xFFFF`; its atlas byte often equals `0xFF` but may contain a stale index. A nonempty tile references an atlas ID in bounds.

The arrays are **not interleaved**. This is important for reconstructing row order. A named `collision` layer is an explicit physics-related map layer, but its nonempty tile IDs **do not by themselves specify solid rectangles versus slopes, one-way platforms, spikes or sensors**.

## Verified coverage

- 213/214 files within `screen-med/maps/` decode precisely to end-of-file: 137 single-layer, 40 two-layer, 36 three-layer.
- All 213 same-named `screen-xlarge/maps/` counterparts are byte-identical to their medium-screen files.
- `gs_background_sky.map` is a structurally different, special-case file and is intentionally rejected by the multilayer decoder.
- `MUMap1-1.map`: 300 columns × 19 rows, 32×32 nominal tiles, layers `map` (1,579 occupied tiles), `collision` (790), and `destructible` (33).
- Exactly 335 cases in the 213 maps have an empty `0xFFFF` tile ID but a non-`0xFF` atlas index; a strict empty-index match would incorrectly reject legitimate files.
- The host unit suite after this step contains 82 synthetic tests, including 19 new tests for maps and IPA CLI.

## Local commands

```sh
PYTHONPATH=src python -m heman_tools.tilemap_cli \
  --ipa /secure/local/He-Man-v2.0.0.ipa \
  --map MUMap1-1.map \
  --out local_reports/level1_tile_layers.json

PYTHONPATH=src python -m unittest discover -s tests -v
```

All derived output belongs in `local_reports/`, which is Git-ignored. Do not commit original or extracted `.map`, `.shape`, `.lvl`, game textures, screenshots, sound, IPA or reports.

## Next investigation

Identify the mapping between numbered collision tiles and actual collision primitives/behaviours; validate orientation and scale against the level-object coordinates; distinguish visual decor from gameplay collision; then build the first safe independent physics prototype.
