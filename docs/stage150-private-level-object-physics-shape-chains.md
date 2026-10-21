# Stage150 — cross-resource evidence from original Level objects to physics and shapes

## Independent, owner-private source observations

Inspected the owner's original iOS v2.0.0 IPA read-only, outside
public GitHub. Compared **fully parsed** `.lvl` object `class_name`
strings with full physics-structure resource basename stems
(`.ps2d` or `.pstruct2d`), and then compared main physics-record
strings with independently validated standalone `.shape` stems.

These are **exact full-string matches** — no fuzzy search, substring
matching, nearest-neighbor geometry guesses or numerical field decoding.
The iOS medium/extra-large resource packs contain matching source
level, physics and shape files byte-for-byte.

| Original iOS source audit | Observed aggregate |
|---|---:|
| Fully parsed level files | **39** |
| Fully parsed level objects | **3,943** |
| Levels with any class-name / physics-resource basename match | **25** |
| Object instances with exact class-name match | **244** |
| Distinct physics-resource stems matching level classes | **12** |
| Those 12 physics resources with validated shape-name references | **12** |
| Physics main-record shape-name references from linked resources | **59** |
| Distinct validated `.shape` stems in this chain | **46** |

### Original first level, examined separately

| Level 1-1 direct resource link | Observed aggregate |
|---|---:|
| Parsed source objects | 159 |
| Objects whose **class name** equals a physics filename stem | **6** |
| Distinct physics file stems directly associated by name | **2** |
| Main physics-record references that match existing shapes | **7** |
| Distinct shape stems reached through those name matches | **4** |

The six first-level instances do not mean six unique physics files:
they reuse two name-matched resources. Conversely, seven shape-string
occurrences are not seven unique or active collision bodies. Four
distinct shape resource names can be traced by this string linkage.

This is stronger evidence than Stage148/149's float32 plausibility:
it joins three **independently parsed resource families**. It does
**not** yet show a runtime call path, authoritative actor/collider
ownership or any in-game physical behavior. The other Level 1-1
objects may use another resource indirection, scripts, visual
animation, a tilemap collision world or no physical collider at all.

## Implemented read-only aggregate gate

New module:
`src/heman_tools/level_physics_shape_chains.py`.

It uses existing bounded parsers:
`parse_level_objects`, `parse_physics_structure` and
`parse_shape`, plus exact duplicate/symlink/screen-pack validation
from previous stages. It emits **counts and fixed capability flags**,
never a level object list, per-object coordinates, original class
identities, resource filenames, original shape vertices, source
payload values or file hashes.

Owner-private command:

```sh
PYTHONPATH=src python -m heman_tools.level_physics_shape_chains \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/level_physics_shape_chains.json
```

`local_reports/` is gitignored. Neither the original IPA nor
extracted source resources enter CI, pull request attachments,
release assets or user-visible game screenshots.

The public suite adds **21 completely invented** level/physics/shape
integration tests, including a fake multi-level paired ZIP,
three-resource chain correctness, strict class matching versus
similarly named classes or typed string properties, absent shape
references, duplicated physics stems, damaged level/physics/shape
formats, screen-pack divergence, duplicate ZIP entries, symlinks and
output redaction.

## Why Switch geometry remains blocked

Exact resource identifiers are structural evidence, but the following
still require independent verification:

- Whether the original engine instantiates a collider for every
  matching object class, and if so in which animation states.
- Whether named shapes are contact bodies, trigger sensors, damage
  volumes, fixed world geometry or merely unused resources.
- How shape-local coordinates are transformed into level-world
  coordinates and how `collision` tile identifiers behave.
- The meaning of opaque 50-byte main-record blocks and typed trailer
  payload values.
- The original player movement/gravity/jump/hitbox behavior, iOS
  rendering and real Nintendo Switch hardware frame pacing.

Next engineering step: on **private only** sources, inspect whether
named physics-structure links co-occur with explicitly typed
level-object properties and source `.shape` kind/flags. Count the
agreement without exporting geometry. Avoid guessing collision
layers or treating any unverified tag as an actual material/sensor
flag. No NRO gameplay changes are justified from string equality alone.
