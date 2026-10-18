# Stage 008 — mask-based landing/jump prototype

This is a **host-side experiment**, not a Nintendo Switch build, and not a verified reconstruction of the original game's full physics.

## Evidence from the user's private iOS 2.0.0 archive

`screen-med/textures/collisionTiles.png` is 192×128 RGBA and partitions into 6×4 slots of 32×32 pixels, indexed in row-major order. The first level's `collision` layer references the `collision` atlas (index 0) for all **790 occupied cells**. The occupied tile IDs are **3, 4, 5, 6, 7, 8**.

At alpha threshold 128, the number of occupied pixels in these tiles is:

| Tile ID | Alpha-occupied pixels / 1024 | Observation |
|---|---:|---|
| 3 | 528 | diagonal/top-edge wedge |
| 4 | 528 | opposite wedge |
| 5 | 1024 | fully filled |
| 6 | 176 | shallow partial wedge |
| 7 | 517 | partial wedge |
| 8 | 859 | largely filled wedge |

Other stage and battle maps use additional IDs (for example 9–11); these **must** be derived from the user's local atlas as needed and are not hardcoded as complete solid squares.

### Physical meaning is provisional

The alpha channel is a useful geometric guide, but it is **not established** that the original runtime uses alpha-threshold collision. Runtime physics may use separate polygons or slope metadata from `.tileset` / `.ps2d`. The following code is an independent approximation for testing algorithms.

## Implemented

- `CollisionMask`: row-bitset representation (1–64 px masks) and safe alpha-threshold conversion.
- `extract_masks_from_alpha`: extract selected row-major masks from a decoded RGBA atlas; source pixels are never committed.
- `MaskedGrid`: fixed tile-grid indexing and pixel-level mask query. Rejects occupied tile IDs without matching profiles.
- `step_actor`: deterministic fixed-timestep horizontal input, gravity, feet collision, ground adhesion within a bounded step-up/step-down window, jump and fall.
- Collision query tests scan every intermediate pixel for downward travel, rather than skipping thin ground at high speeds.
- `collision_probe`: optional private IPA diagnostic (requires locally installed Pillow). It does not extract or publish source assets.

**Not implemented:** side collisions, overhead collisions, box-shaped character body, moving objects, interactions, edge cases of slopes, original player physics constants, enemies, animation, or Switch input/output.

## Testing

After this stage, the host suite contains **100/100 synthetic tests** (18 new); all tests run without Pillow, IPA or proprietary artwork.

Private integration test on `MUMap1-1.map` using the actual local alpha atlas:
- Layer size 300×19, tile size 32, 790 occupied collision cells.
- Successfully generated all six masks from the local archive, with no missing atlas profiles.
- A noninteractive falling-foot probe at X=50, starting Y=0, simulated 240 frames at 60 Hz. It landed with feet Y=448 in the *prototype's* coordinate system. This is not evidence of actual level spawn coordinates or engine physics.

## Run privately

```sh
# Python 3.10+; optional local-only dependency for PNG decoding:
python -m pip install Pillow

PYTHONPATH=src python -m heman_tools.collision_probe \
  --ipa /private/He-Man-v2.0.0.ipa \
  --map MUMap1-1.map --x 50 --start-y 0 --ticks 240 \
  --out local_reports/level1_mask_probe.json

PYTHONPATH=src python -m unittest discover -s tests -v
```

All private reports should be stored under `local_reports/` (Git-ignored). Do not commit the purchased IPA, map files, collision atlas PNG, extracted pixels or derived per-level visuals.

## Next step

Find and validate the original collision logic and player collider dimensions, and add horizontal/overhead collision handling to the independent physics harness. Only then consider full player movement and Nintendo Switch NRO integration.
