# Stage257 — collision-atlas alpha census

## Purpose

Stage057 and Stage074 measured collision-layer occupancy and connected components, but those measurements did not compare occupied tile IDs to the alpha masks of the corresponding atlas rectangles. Stage257 adds a read-only, owner-local census that joins the parsed `.map` collision layer, the serialized `collision.tileset` rectangle table, and the candidate `collisionTiles.png` alpha channel.

The tool reads ZIP entries directly from the original IPA in memory. It does not extract resources, export tile coordinates, or write any original bytes. Detailed per-tile measurements are written only beneath the Git-ignored `local_reports/` directory.

## Private owner-IPA observation

The original Level 1-1 collision layer contains **790 occupied cells** and six used tile IDs. Every occupied cell in this map references the `collision` atlas entry. The two screen packs contain byte-identical `MUMap1-1.map` files.

The medium- and xlarge-screen tilesets have the same record names and rectangle layout after a uniform 2× scale adjustment. Across the six used tile IDs, the maximum absolute difference in the fraction of atlas pixels with alpha ≥ 128 is **0.006104** (about 0.61 percentage points). This supports the interpretation that the selected atlas rectangles are aligned across the two resolution packs.

One used tile ID occurs in 754 cells and its medium-pack atlas rectangle has alpha ≥ 128 across all 1,024 pixels; its xlarge counterpart is also fully covered at the same threshold. The other five used IDs have partial alpha coverage. These are observations about serialized atlas data, **not** proof that a tile is physically solid, a slope, one-way terrain, a hazard, or an active collider.

The detailed owner-private report and source hashes are preserved separately in the private project archive. No original tile grid, texture, per-cell coordinate, IPA byte, or private report is included in the repository or CI artifacts.

## Local command

Run from the repository root with Python 3.10+ and Pillow installed:

```sh
PYTHONPATH=src python -m heman_tools.collision_atlas_alpha \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --map MUMap1-1.map \
  --compare-screens \
  --out local_reports/level1-collision-atlas-alpha.json

PYTHONPATH=src python -m unittest discover -s tests -p 'test_collision_atlas_alpha.py' -v
```

The CLI validates the map, tileset and PNG bounds, rejects duplicate IPA entries, checks exact map-byte parity, and compares normalized alpha coverage. It writes only a private JSON summary. Public CI uses fabricated map, tileset and PNG fixtures and never loads the original IPA.

## Evidence boundary

The alpha census does **not** establish:
- collision response or which pixels the original engine samples;
- one-way platforms, slopes, hazards, sensors or destructible behavior;
- world scale, coordinate orientation, object ownership or actor hitboxes;
- equivalence with original iOS gameplay traces;
- authorization to import these masks into the Switch gameplay engine.

The next step is to connect these alpha observations to the original engine's tile/collision lookup path and independently observed gameplay behavior. Until that linkage is established, collision masks remain research evidence and are not imported into the native Switch prototype.
