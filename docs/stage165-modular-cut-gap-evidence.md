# Stage165 — modular geometry of registered sprite-cut lexical anchors

**Status:** research diagnostic only; not a frame decoder or an NRO
asset importer. This PR is stacked on Stage164 (same-length decoy
negative controls). Original iOS assets remain owner-private.

## Testable structural hypothesis

Stages158–164 established strict source index/record checks and
validated the difference between lexical registered cut names and
unregistered same-length decoys. Stage165 measures **only** the byte
length of the opaque region between adjacent independently registered
names, and the trailing region after the final such name but before
the separately validated final u32.

The Stage158 candidate stride of 82 bytes is now evaluated in a more
permissive setting that does **not** assume any number of nested frames
or one sprite-cut reference per declared candidate.

For each known-first-name record:

1. Scan for later registered cut tokens using the exact bounded
   length-prefixed UTF-16 name matcher from Stage163.
2. Measure the non-overlapping opaque gaps between the *end* of one
   registered name and the *start* of the next.
3. Assign each gap to an exact modular candidate family:
   `76 + 82n`, `97 + 82n`, `118 + 82n`, or other.
4. Independently test the terminal opaque tail against `64 + 82n`.
5. For **nonbaseline** terminal tails longer than 64 bytes, compare
   exact hits for stride 82 against the neighboring strides **81 and
   83**. Baseline 64-byte tails are not counted as evidence that
   distinguishes stride hypotheses.
6. Compare complete private per-record gap sequences between the two
   source-resolution packs and expose **only grouped counts**.
7. Reconcile known-first-name totals, presence of later real names and
   count-group strata against the independent Stage164 source checks.

Do not read these equations as documented original structure. They
are falsifiable modular hypotheses. If source data contain gaps
outside them, preserve those counts in an explicit `other` bucket;
never silently ignore exceptions or imply a full grammar parse.

## Privacy and reproducibility

- Code: `src/heman_tools/sprite_sequence_modular_anchor_geometry.py`
- Synthetic-only tests:
  `tests/test_sprite_sequence_modular_anchor_geometry.py`
- All public CI fixtures are fabricated. They include positive modular
  matches, off-by-one negatives, unrelated incidentally matching tokens,
  two different screen-pack layouts, malformed source metadata and
  unsafe ZIP members.
- **No original token, asset name, offset, per-record gap sequence,
  raw numeric field, sprite bytes, frame image or original IPA** is
  uploaded to this repository or its Actions.

Run in the owner's private environment:

```sh
PYTHONPATH=src python -m heman_tools.sprite_sequence_modular_anchor_geometry \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_sequence_modular_anchor_geometry.json
```

The `local_reports/` path is ignored by Git. A separate owner-only
local source census may independently corroborate the aggregate
modular categories but must not be committed.

## What success or failure means

Constrained modular gaps across both iOS resolution packs support
a repeated binary serialization pattern. A stronger hit rate for 82
than 81 or 83 on **nonbaseline** source tails supports a byte stride
of 82 as a candidate component size.

Neither result proves the 82-byte component is one animation frame,
nor that a word called `count` counts frames. Durations, ordering,
object bindings, looping and hitbox transitions still need independent
runtime or format evidence before importing original sprites to Switch.

The synthetic Nintendo Switch NRO remains unchanged.
