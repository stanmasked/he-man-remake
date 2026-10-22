# Stage166 — falsify equivalence of unknown count, cut names and 82-byte extensions

This is a source-structure test for the owner's original iOS IPA,
**not** an original animation decoder or a Switch asset pipeline.

## Why this test follows Stage165

The previous Stage165 exact indexed sprite-cut names expose:
- An independently serialized unknown candidate-count u32
- A number of independently indexed registered cut-name tokens
  within each record (initial registered name + later registered names)
- Opaque inter-name gap and terminal-tail lengths that may conform
  to candidate modular categories

All of these are observable, but **none is independently proven** to
count rendered animation frames. A repeated 82-byte step may be a
serialization component unrelated to frame timing or identity.

## Two falsifiable comparisons

**A. Registered cut-name references vs unknown u32:** when the initial
cut name is in the separately validated cut registry, compare
`1 + later_exact_indexed_name_hits` against the unknown u32.
Count only the three anonymous classes `less / equal / greater`.

**B. Hypothetical 82-byte extensions vs unknown u32:** classify a
record only if *every* inter-name gap matches one of Stage165's three
declared `76 / 97 / 118 + 82n` families and the final opaque region
matches `64 + 82n`. Sum **only the extra 82-byte units** after
subtracting those independent bases, then compare that number against
the unknown u32 as `less / equal / greater`.

Do **not** call this number a frame count. Do **not** silently count
unknown or unmatched gap lengths as zero. If any gap fails, the record
is classified `unclassifiable_under_82_geometry` instead.

Additional explicit falsification counters preserve records where:
- Unknown u32 == 1 but more than one registered name appears
- Unknown u32 == 1 but positive extra 82-byte increments appear
- Unknown u32 > 1 but zero extra 82-byte increments appear

## Verification and privacy

- Reuses Stage165's strict source pack validation, lexical controls,
  independent SpriteCutData registry, screened original IPA ZIP readers,
  paired-resolution record index validation and gap/tail category census
- Reconciles known initial names, later name counts, number of lexical
  gaps and pack-to-pack gap equality with Stage165 aggregate totals
- Exports **only cross-tabulated aggregate counts** by first-u32=1 /
  other and the independent unknown-count buckets
- Neither names nor raw u32 values, offsets, exact per-record gap
  lengths, opaque pixels, IPA bytes or records are included in output
- Twenty fabricated-only source tests cover all three comparisons,
  positive and zero-length hypothetical extensions, unmatched gaps,
  cross-resolution controls, redaction and ZIP archive safety

Files:
- `src/heman_tools/sprite_sequence_count_vs_modular_units.py`
- `tests/test_sprite_sequence_count_vs_modular_units.py`

Private owner-only invocation:

```sh
PYTHONPATH=src python -m heman_tools.sprite_sequence_count_vs_modular_units \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_sequence_count_vs_modular_units.json
```

All private results must remain in ignored `local_reports/` or another
private local analysis location, never in GitHub or Actions.

## Interpretation

Any disagreement refutes a naive assertion that the field, the
number of registered references and the number of 82-byte extensions
are interchangeable. Even perfect agreement would **not prove**
actual frame count, frame duration, animation state, playback order or
hitbox transitions. These require independent game serializer or
runtime evidence.

The synthetic Switch NRO and public gameplay code remain unchanged.
