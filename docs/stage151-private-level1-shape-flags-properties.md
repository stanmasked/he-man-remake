# Stage151 — first-level linked shape flags and typed object properties

## Original iOS evidence, inspected privately

This stage inspects the user's original He-Man iOS v2.0.0 IPA **read-only**
outside public GitHub. It extends Stage150's **exact-name resource chain**:
`LevelObject.class_name` → `.ps2d` / `.pstruct2d` filename stem →
string reference in a decoded main physics record → verified `.shape`
filename stem. These are **file-level textual matches**, not runtime
collision ownership.

For the original first level, the private aggregate inspection found:

| Measurement | Owner-private aggregate |
|---|---:|
| Decoded level objects | **159** |
| Objects whose classes match physical resource stems | **6** |
| Distinct matching physics resources | **2** |
| Matching physics-record shape-name references | **7** |
| Distinct referenced valid shape resources | **4** |
| Referenced polygons | **4** |
| Referenced circles | **0** |
| Four-vertex polygons among them | **4** |
| Referenced figures with serialized flags equal to 1 | **4** |
| Referenced figures with nonempty embedded reference strings | **4** |
| Embedded references exactly matching linked actor identities | **0** |

All four shape primitives are *four-vertex polygons* with an observed
flag value of **1**, but flag 1 is **not unique to this first level**.
Across the **409** original global `.shape` resources, **38** are
four-vertex polygons with the same observed flag value. The complete
global library includes 347 polygons and 62 circles. The serialized
flag value is not enough to conclude whether a figure is solid,
a trigger sensor, a damage volume, a decorative boundary or unused.

### Typed properties on the six linked level objects

| Owner-private object metadata | Count |
|---|---:|
| Linked objects with no typed properties | **1** |
| Linked objects with exactly one typed property | **5** |
| Linked objects with multiple typed properties | **0** |
| String-typed property occurrences on linked objects | **5** |
| Boolean, integer or float typed properties on linked objects | **0** |
| String values equal to existing physics resource basename stems | **0** |
| String values equal to existing shape basename stems | **0** |
| Linked objects with identity-like linear affine component | **6** |

The actual property keys, values, object identities, matrices,
coordinates, full shape vertices and flags of individual resource
files remain **private**. A match or mismatch of source names is not
proof of original runtime object-to-hitbox binding.

## Implementation and test boundary

Added `src/heman_tools/level1_shape_flag_properties.py`, reusing
existing original-format parsers:

- Parse the original first level's object table and typed properties.
- Parse each paired `physics_struct` main record and its shape strings.
- Fully validate the paired standalone shape resources.
- Count only *distinct* linked shape names, so repeated references
  do not inflate the number of physical resources.
- Compare the linked four-vertex/flag-1 shape count against the
  **entire original shape catalog**, avoiding a misleadingly special
  interpretation of a common serialized flag.
- Check *literal* typed string values and shape embedded reference
  text against linked metadata, without fuzzy name matching.
- Mark original collisions, triggers, sensors, player hitboxes and
  Nintendo Switch geometry import **unverified / not authorized**.

The owner-local command is:

```sh
PYTHONPATH=src python -m heman_tools.level1_shape_flag_properties \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/level1_shape_flag_properties.json
```

The `local_reports/` directory remains ignored by Git. The summary
contains aggregate counters and fixed unverified flags only; no
source game artwork, geometry arrays, individual object coordinates,
property strings, original file hashes or copied asset bytes may
enter GitHub. Public CI uses **24 wholly invented** physics/shape/
level fixtures and synthetic two-resolution ZIP test archives.

## Outstanding work before original gameplay reconstruction

The next defensible step is to examine the six matched actor classes'
resource references and animation-state linkage in a source-local
manner, plus independently verify the original physics meanings via
gameplay/video reference. Until then, do not import the original
shapes as collision polygons into the synthetic Switch NRO or
declare verified object hitboxes based on metadata alone.
