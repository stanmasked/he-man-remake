# Stage 065 — private cross-report integrity audit for first-level geometry

Several local tools can independently inspect candidate evidence from the user's
original iOS archive. Before treating any result as an actionable geometry
hypothesis, their reports must agree about **level identity, screen resource
pack, selected map name and collision-layer structure**.

This stage cross-checks three existing private JSON reports:

1. `level_map_links` — exact text candidates between `.lvl` map objects and
   archive `.map` names.
2. `shape_object_candidates` — exact text candidates between decoded level
   objects and local `.shape` names/references.
3. `collision_inventory` — counts of *nonempty candidates*, not solid tiles,
   from a selected `collision` layer.

For a selected map, the audit requires one matching structural report and
checks whether exactly one level object has a single exact textual reference
to it, whether there is exactly one named `collision` layer, and whether
occupied + empty grid cells equal columns × rows.

**Inconsistencies reject the report.** Missing or ambiguous references are
recorded as blockers. Even a structurally consistent report always retains
`authentic_collision_verified: false` and
`automatic_collision_export_permitted: false`.

## Private commands

Run these commands from the local repository root, with the original game
archive held privately. The following reports remain inside gitignored
`local_reports/`; do **not** commit them:

```sh
PYTHONPATH=src python -m heman_tools.level_map_links \
  --ipa /private/He-Man-v2.0.0.ipa \
  --level MULevel1-1.lvl \
  --screen screen-med \
  --out local_reports/level1-map-links.json

PYTHONPATH=src python -m heman_tools.shape_object_candidates \
  --ipa /private/He-Man-v2.0.0.ipa \
  --level MULevel1-1.lvl \
  --out local_reports/level1-shapes.json

PYTHONPATH=src python -m heman_tools.collision_inventory \
  --ipa /private/He-Man-v2.0.0.ipa \
  --map MUMap1-1.map \
  --screen screen-med \
  --out local_reports/level1-collision.json

PYTHONPATH=src python -m heman_tools.first_level_report_audit \
  --links local_reports/level1-map-links.json \
  --shapes local_reports/level1-shapes.json \
  --collision local_reports/level1-collision.json \
  --out local_reports/level1-cross-report-audit.json
```

The map name above is a candidate found in earlier private investigation,
not a proven physical collision-map assignment. If the report does not show
a unique candidate association, treat that as an unresolved dependency.

This utility does **not** read the IPA itself. It reads three bounded
private JSON files and writes only a private summary. 18 public tests use
synthetic summaries and exercise mismatches, ambiguity, corrupt counters,
unsupported source claims, and private-path protection. They contain no
commercial game bytes or derived real geometry.

## Evidence boundary

A cross-report match is **not an independent observation** of gameplay.
It does not validate manual shape ownership, tile properties, physical scale,
camera model, original movement and collision rules, or a completed first
level. The existing eight-category manual evidence gate remains necessary.
No Switch core/gameplay code is changed by Stage 065.
