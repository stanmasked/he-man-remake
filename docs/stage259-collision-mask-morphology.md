# Stage259 — collision atlas alpha-mask morphology

## Purpose

Stage257 established that the first-level collision map points to a six-ID candidate atlas and that the medium/xlarge rectangle layout is uniformly scaled. Stage259 adds a local-only morphology report for the alpha-threshold mask of each tile ID actually used by the collision layer.

For each used tile, the report records the alpha-covered bounding box, top/right/bottom/left edge coverage, horizontal and vertical runs, exposed four-neighbor boundary-edge count, and row/column occupancy profiles. The medium and xlarge masks are compared after block-majority downsampling to the medium resolution. Both source masks remain in memory; the report contains no raw pixel mask or map cell grid.

## Local command

Run from the repository root with Python 3.10+ and Pillow installed:

```sh
PYTHONPATH=src python -m heman_tools.collision_mask_morphology \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --map MUMap1-1.map \
  --out local_reports/level1-collision-mask-morphology.json

PYTHONPATH=src python -m unittest discover -s tests -p 'test_collision_mask_morphology.py' -v
```

The tool reads the IPA directly without extracting any entry, validates all tileset rectangles against texture bounds, caps per-tile morphology work at 1,048,576 pixels, and requires a uniform rectangle scale across the two packs. It writes detailed profiles only beneath the Git-ignored `local_reports/` directory.

## Owner-private original source result (aggregate only)

A read-only run against the canonical private iOS v2.0.0 IPA completed. The two resolution packs have byte-identical Level 1-1 map entries and a uniform 2× tileset-rectangle scale. Across six used collision tile masks, four normalized threshold masks match exactly; the remaining two differ by one pixel each. That is **2 mismatched pixels out of 6,144**, with aggregate intersection-over-union **0.9994494908**.

The full row/column profiles, per-tile edge counts and source hashes are preserved in the owner-only [Stage259 private Drive handoff](https://docs.google.com/document/d/1owo-ARjqB783pCNkp_D9UhQNyNy2FMDVUJEURq_QmOY/edit). Only aggregate metrics are published here. Close mask agreement is not proof that the original engine uses alpha as collision or that any mask is a solid, slope, one-way platform or hazard.

## Interpretation boundary

Morphology can describe the image mask and whether it stays consistent between resolution packs. It cannot by itself prove that the original engine treats alpha as collision, nor identify a solid body, slope, one-way surface, hazard, sensor, destructible region, object owner, world transform or collision response.

The normalized mask comparison deliberately reports disagreements instead of silently resampling or normalizing them away. A completed structural report is not the same as exact mask parity and neither is proof of gameplay behavior.

## Public test boundary

The new regression suite uses fully synthetic multilayer maps, tileset records and generated PNGs. GitHub Actions never downloads or opens the original IPA and stores only a synthetic capability summary for seven days. The report explicitly keeps original collision semantics, iOS gameplay trace parity and native Switch collision import unverified.

## Next gate

After the owner-local Stage259 report is reviewed, use the morphology profile to select a small set of candidate tile masks for a separate original-engine lookup investigation. Require an independent source call path or observed gameplay evidence before assigning any physical meaning. Do not import these masks into the Switch NRO at this stage.
