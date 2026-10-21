# Stage140 — private iOS physics-structure → geometry identifier census

## Confirmed source-private observation

I inspected only the owner's original `He-Man-v2.0.0.ipa` in a
private workspace. The `screen-med` and `screen-xlarge` variants
contain **81 corresponding physics structure resources**, and all 81
pairs are byte-identical. The **409 decoded `geometry/*.shape` files**
are likewise byte-identical between the two packs.

A deliberately conservative scan searched each physics structure for
an exact **little-endian 16-bit UTF-16 code-unit length followed by
a complete UTF-16LE shape-filename stem**:

| Offline aggregate | Result |
|---|---:|
| Physical-structure resources considered | 81 |
| Resources with at least one exact shape-stem candidate | 71 |
| Distinct resource–shape candidate pairs | 137 |
| Distinct shape stems appearing in physics resources | 112 |
| Shapes whose stems appear in the geometry registry metadata | 400 / 409 |
| Physics-referenced shape stems absent from registry | 0 |

These are *lexical byte-pattern coincidences*, not decoded `.ps2d`
field references and not a verified runtime call graph. The registry
result likewise indicates consistent candidate naming, not proven
resource loading. The remaining **nine shapes** may have different
registration conventions, be unused, or be reached through another
scheme; we cannot infer their gameplay status.

The private evidence suggests a more productive research route than
direct Level 1-1 object-name comparisons:
**level objects → resource/physics structure → global geometry
registry → shape primitive**. Only the last two *lexical* stages
currently have positive aggregate evidence; the arrows themselves
remain unverified.

## Reproducible read-only local audit

```sh
PYTHONPATH=src python -m heman_tools.physics_shape_census \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/physics_shape_census.json
```

This tool validates 409 original shape primitives with the existing
format parser, cross-checks paired physics files, compares metadata
registry contents and scans strictly length-prefixed UTF-16 sequences.
It never writes or extracts the original assets. Every archived
resource read is size-bounded and symlink/duplicate entries fail
closed.

The report contains **counts and fixed flags only**. It never emits
shape names, physics filenames, registry contents, individual
source hashes, decoded vertices, tile layouts or object positions.
The file stays under the ignored private `local_reports/` folder.
Public GitHub Actions must run only the 14 fabricated ZIP/shape
tests, never the original IPA.

## What remains genuinely unknown

1. Which exact fields of `.ps2d` and `.pstruct2d` refer to shape
   geometry and which refer to purely visual or gameplay helpers?
2. How does each original Level 1-1 object select its physics
   structure? This is not proven by text patterns or matching
   resource filenames.
3. Which shapes are active sensors, hitboxes, damage volumes,
   platforms, static colliders or decorations?
4. How are local shape coordinates transformed into game-world and
   screen positions? Stage139's candidate 32-unit alignment does
   **not** prove the actual runtime transform.
5. What can be validated without an original working iOS device?

The present Switch NRO remains an independently authored technical
level laboratory. No automatic collision import, hardware parity
claim or original game-rule claim is justified yet.
