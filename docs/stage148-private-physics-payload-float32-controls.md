# Stage148 — float32 interpretation controls on typed iOS physics payload bytes

The owner's private original `He-Man-v2.0.0.ipa` was inspected locally,
read-only, without publishing the IPA or any extracted names, coordinates,
payloads, original binary values or gameplay assets.

Stage147 had identified exact structural boundaries for **44** opaque
trailer records across 13 source files. These have byte payloads of
33 (variant 0), 25 (variant 1), and 34 (variant 2) bytes, excluding
their already parsed 4-byte variant discriminators.

## New evidence: compare *all* float32 alignments and both byte orders

To avoid inventing numerical fields, this stage checks **four**
starting positions (0, 1, 2 and 3 bytes into each opaque payload)
and both IEEE754 float32 byte orders. Each interpretation consumes
full four-byte lanes only. All exact zeros are counted separately
from nonzero values, which are deemed within an arbitrary diagnostic
window only when **1e-8 <= abs(value) <= 1e4**. These limits are
engineering heuristics, **not original physics bounds**.

### Actual owner-private aggregate observations

| Typed record | Count | Opaque bytes | Candidate | Values within heuristic window, including zero |
|---|---:|---:|---|---:|
| Variant 0 | 22 | 33 | Offset 0, little-endian | 39 / 176 |
| Variant 0 | 22 | 33 | Offset **1**, little-endian | **139 / 176** |
| Variant 0 | 22 | 33 | Offset 1, big-endian | 53 / 176 |
| Variant 1 | 13 | 25 | Offset 0, little-endian | 16 / 78 |
| Variant 1 | 13 | 25 | Offset **1**, little-endian | **65 / 78** |
| Variant 1 | 13 | 25 | Offset 1, big-endian | 25 / 78 |
| Variant 2 | 9 | 34 | Offset 0, little-endian | 29 / 72 |
| Variant 2 | 9 | 34 | Offset **1**, little-endian | **47 / 72** |
| Variant 2 | 9 | 34 | Offset 1, big-endian | 40 / 72 |
| Variant 2 | 9 | 34 | Offset 2, little-endian | 40 / 72 |

**Important:** A large plausibility count is **not proof of float32
field type, units, coordinate origin or collision semantics**. Random
bytes and zero padding can generate plausible or tiny IEEE754 values,
and the remaining offsets/byte orders also have samples in-range.
Variant 2 has no convincing unique offset from this criterion. Variant
0 and 1 suggest a *candidate* byte alignment at 1 that can be
independently investigated, not used as a discovered field map.

The private sample set also contains **10 distinct** variant-0
payload byte patterns among 22 records, **9 distinct** variant-1
patterns among 13, and **7 distinct** variant-2 patterns among 9.
These are aggregate diversity counts, not a decoded physics schema.

## Implemented source-only diagnostics

`src/heman_tools/physics_payload_numeric_controls.py` extends
Stage147's **strict typed-record boundary validation**. All real
opaque payloads stay temporarily in memory. The scanner compares
four starting offsets and both little-/big-endian float32
interpretations, counts exact zero / nonzero-in-window / small /
large / non-finite values, and never publishes individual values.

Owner-private audit (never use the original IPA in GitHub Actions):

```sh
PYTHONPATH=src python -m heman_tools.physics_payload_numeric_controls \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/physics_payload_numeric_controls.json
```

The optional report belongs under gitignored `local_reports/`
and has only aggregates and hard-coded `false` runtime assertions.
The **21 public regression tests** are all invented physics records
and synthetic paired ZIP archives. No original resource bytes or
individual source-derived floating-point values enter the PR.

## What we have *not* proven

- The payload contains real-world or game-world float32 fields.
- A signed or unsigned type for the leading payload byte(s).
- Any meaning for the variant discriminator codes 0, 1 and 2.
- Any relationship to a particular Level 1-1 actor or shape.
- The meaning of the separate 50-byte main physics-record payload.
- Physical Nintendo Switch or original iOS gameplay parity.

**Next useful test:** examine cross-record invariants and deliberately
contradictory byte/float interpretations using independent structural
references. Require evidence that constrains offset, type and semantic
role consistently; never turn plausible numeric values into automatic
source-geometry imports.
