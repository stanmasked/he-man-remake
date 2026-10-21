# Stage138 — original iOS Level 1-1 structural readiness gate

## Confirmed offline from the owner's private iOS v2.0.0 archive

A bounded read-only inspection of the **actual privately held IPA**, with no
resource copied to public GitHub, established the following Level 1-1 file
structure across both resource screen packs:

| Structural evidence | screen-med | screen-xlarge |
|---|---:|---:|
| `MULevel1-1.lvl` bytes | 30,321 | 30,321 |
| Native level object-table count | 159 | 159 |
| `MUMap1-1.map` bytes | 51,825 | 51,825 |
| Number of decoded layers | 3 | 3 |
| Tile grid dimensions | 300 × 19 | 300 × 19 |
| Nonempty `map` cells | 1,579 | 1,579 |
| Nonempty `collision` cells | 790 | 790 |
| Nonempty `destructible` cells | 33 | 33 |
| Four-connected occupied `collision` regions | 20 | 20 |

In the occupied collision grid there are 20 **four-neighbor-connected** regions (largest: 102 occupied cells; one isolated cell). These are topology-only measurements, **not** 20 separately physical obstacles.

The three-layer parser reached the precise end of both `.map` entries
without extra bytes, and the two screen packs matched. These are **file
layout and occupancy measurements**, NOT physical tile solidity, original
enemy AI, animation, or one-way platform rules. The level table count is
taken from the decoded level header and is not, by itself, independent
validation of every object property.

## Composite local-only gate

`src/heman_tools/first_level_readiness.py` combines already established
read-only, original-archive inspectors rather than guessing new semantics:

- Stage72 exact-byte comparison of the selected `.lvl` and `.map` pair.
- Stage96/97 explicit `mapFileName` candidate link cross-check, including
  the primary and overlay map classes; textual links do not prove that
  original iOS code uses those maps at runtime.
- Stage74 connected-component **occupancy** cross-check of both `collision`
  layers, without exporting cell coordinates or component bounding boxes.
- Complete Stage003 counted object parsing and Stage004 named-point
  graph parsing, including bounds-checked link indices.

For the owner's private archive:

```sh
PYTHONPATH=src python -m heman_tools.first_level_readiness \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/level1_readiness.json
```

All detailed source data remain in memory and no original game assets,
map tiles, collision polygons, individual class names, resource-linked
filenames, coordinates, bytes or hashes go to report output. Only
aggregate counts, fixed booleans and **fixed non-private engineering
questions** are emitted. The report directory is gitignored; never
send the original IPA or private extracts to CI or GitHub issues.

Even if every structural check passes, the tool **always** marks:
`ready_for_automatic_collision_import: false`,
`real_ios_gameplay_fidelity_verified: false`. This is deliberate.
Geometric source interpretation needs private visual/trace validation
before we can map the user's game onto the prototype engine.

## Remaining blockers (genuinely unknown)

1. Which occupied source tile types are solid, sloped, one-way, damage
   hazards or purely decorative? No mapping of tile IDs to physical
   meaning is authorized by the file structure alone.
2. Does each level-object transform use the same pixel/world scale as
   the `collision` tile grid, and what are the camera transforms?
3. Which `.shape` local polygons/circles bind to which object sprites?
   A shape name or shared basename does not independently establish
   runtime object ownership or collision semantics.
4. What are exact iOS jump speeds, gravity, attack hitboxes, moving
   platform rules, enemy AI, scripted events and camera behavior?
5. What evidence can replace an original iOS device gameplay capture?
   Without that, game-rule parity remains **unverified**.

Next engineering step: generate **synthetic-only coordinate alignment
hypotheses and tests** using a hypothetical test tile grid, without
publishing the real game's geometry or turning any hypothesis into
an original-physics claim. Any future private import should require
an explicit validated transformation and a human-reviewed level
rendering/behavior comparison. No device-level claim yet.
