# Stage139 — Level 1-1 object coordinate envelopes and global .shape library

This is a **privately run, read-only research stage**, using the owner's
original iOS v2.0.0 archive **outside GitHub**. No original transforms,
shape vertices, object identities, filenames or copyrighted bytes are
committed. The tests shipped in public source contain only invented data.

## 1. Observations from actual private Level 1-1 metadata

The source `MUMap1-1.map` contains 300 columns and 19 rows. All three
layers serialize tile sizes **32 × 32**. Thus one *candidate*
origin-zero scale interpretation produces an **extent of 9,600 × 608
serialized units** (not necessarily original runtime physics units).

A private inspection of all 159 fully parsed object transform
translations gave these **aggregate candidate envelope counts**:

| Coordinate interpretation (both origin 0) | Objects inside | Outside |
|---|---:|---:|
| 300 × 19 direct grid indices | 3 | 156 |
| 9,600 × 608 serialized tile-size extent | 142 | 17 |

**This is evidence for a plausible scale hypothesis, not a proof.**
Objects outside candidate bounds may be scripted, off-stage, decorative,
camera-anchored, negative-height placement or simply use a different
coordinate frame. We cannot assume one tile in the iOS game truly
corresponds to a 32-unit solid physics box, or that screen y grows
downward, based on these counts.

## 2. Global geometry shape library and lexical evidence

In both private `screen-med/geometry/` and
`screen-xlarge/geometry/` the audit found **409 paired `.shape`
entries**, and all 409 pairs were byte-identical. This is the **global
geometry library**, not 409 collision objects in Level 1-1.

Of the 409 decoded entries, **94** have an embedded reference string.
A conservative *exact-text only* search found **zero matches** from
those embedded references to the 159 level objects' class, group or
instance identities. It also found no exact match between shape
filename stems and those object identities or their typed string
property values.

Those negative matches demonstrate that assigning collision shapes
to level objects by coincident text would be unfounded. They do not
rule out resource lookup via animation files, script indices,
hierarchical scene nodes or another original-game indirection.

## 3. Reproducible PRIVATE-only aggregate gate

With an owner-local copy of the IPA and Python 3.10+:

```sh
PYTHONPATH=src python -m heman_tools.level1_coordinate_shapes \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/level1_coordinate_shapes.json
```

The tool uses existing bounded original-format parsers for Level1-1
objects and multilayer map, and decodes the paired private global
`.shape` libraries without extraction. It rejects duplicate ZIP
members, symlink resources, missing pack peers, size-limit violations
and cross-pack data divergence.

The report contains only **counts and fixed boolean hypotheses**:
nothing from original object placement, shape vertex arrays, resource
filenames, hashes or other original game content. `local_reports/`
is already gitignored. Do not publish the private IPA or an extracted
asset as an Actions artifact.

No matter how well coordinates fit a candidate extent or how many
names happen to match, the reporter fixes
`original_game_coordinate_system_proven: false`,
`native_switch_world_geometry_import_authorized: false`,
`original_gameplay_parity_verified: false`.

## 4. Next requirements before a faithful Switch level

- Establish actual level-to-world affine scale, translation and y-axis
  orientation independently, using original visual/gameplay reference.
- Determine whether collision tile IDs imply solid, sloped, one-way,
  hazard or nonphysical decoration. Occupancy alone cannot do so.
- Trace shape lookup through the game's resource indirection rather
  than guessing via basename or animation label.
- Compare enemy, player movement, hitbox and camera behavior from
  privately inspected original evidence with source-authored Switch
  frames. The absence of an old iOS device limits live comparison.
- Preserve per-level original data and any private comparisons outside
  GitHub; only reusable and demonstrably asset-free tooling belongs
  in the public project.

**This stage is not yet a port or graphical remake.** It narrows an
engineering hypothesis while preserving the separation between the
original game and the independently authored homebrew test level.
