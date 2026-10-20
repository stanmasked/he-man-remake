# Stage 057 — private collision-tile candidate inventory

A named `collision` layer is now readable from the local iOS v2.0.0 IPA, but occupied cells **do not establish which surfaces are solid or how collision works**. This read-only tool inventories candidate tile/atlas IDs and their immediate grid context without creating gameplay geometry.

## Measurements

For each occupied (atlas index, tile ID) pair, the tool counts:
- Number of occupied cells.
- Histogram of how many of the four neighboring grid positions are also occupied (0 through 4).
- Cardinal grid sides bordering either an empty tile or the outside of the map.

A `0xffff` tile ID is empty even if it carries a stale atlas ID. Neighbor counts are geometric *adjacency between nonempty cells only*, never a collision or walkability test. Tile atlas names and numeric IDs are kept only in the user's private JSON report; the raw tile grid is not exported.

## Local command

Run from the repository root with Python 3.10+:

```sh
PYTHONPATH=src python -m heman_tools.collision_inventory \
  --ipa /private/He-Man-v2.0.0.ipa \
  --map MUMap1-1.map \
  --out local_reports/level1-collision-inventory.json

# Compare screen-med and screen-xlarge data (private structural parity check).
PYTHONPATH=src python -m heman_tools.collision_inventory \
  --ipa /private/He-Man-v2.0.0.ipa \
  --map MUMap1-1.map \
  --compare-screens \
  --out local_reports/level1-screen-parity.json

PYTHONPATH=src python -m unittest discover -s tests -v
```

The output path must be a JSON file beneath the current `local_reports/` directory (ignored by Git); the command prints only the number of candidate cells. The program does not upload the IPA or any extracted bytes, and GitHub CI tests use an entirely fabricated multilayer map stored in a temporary fabricated IPA.

## Cross-screen verification

The optional `--compare-screens` mode checks the same named map in both
resource packs. It records two distinct results: **exact original map byte
equality** and equality of derived candidate statistics. The byte check is
stricter because distinct layouts can coincidentally have the same aggregate
statistics. A mismatch is recorded as evidence of uncertainty, not silently
normalized. Missing or duplicated archive entries are rejected; no original
map bytes, raw grids or original art are written to the report.

## Evidence still required

Compare candidate IDs privately against atlas alpha masks, decoded `.shape` primitives, object transforms and measured gameplay behavior. Establish orientation, scale, object-to-geometry ownership and the meaning of individual IDs before converting occupancy into any native collision mask. Preserve all original game binaries, imagery, audio, maps and derived reports outside public GitHub.
