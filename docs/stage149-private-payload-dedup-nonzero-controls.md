# Stage149 — remove duplicate and zero-inflated float32 false positives

This stage continues read-only research into the owner's private
iOS v2.0.0 IPA, outside public GitHub. Stage147 established typed
record boundaries. Stage148 compared tentative float32 values but
included exact zeros and repeated payloads.

## Actual original iOS private aggregates

There are 44 typed trailer records across 13 original physics files.
The two screen resolution packs have corresponding equal resource
bytes. These 44 observations include repeated exact binary payloads:

| Code | Occurrences | Distinct entire payload byte patterns | Repeat copies |
|---|---:|---:|---:|
| Variant 0, 33 opaque bytes | 22 | 10 | 12 |
| Variant 1, 25 opaque bytes | 13 | 9 | 4 |
| Variant 2, 34 opaque bytes | 9 | 7 | 2 |
| Total | 44 | 26 (within variants) | 18 |

Candidate float32 values are interpreted at offsets 0, 1, 2, 3
and in both little- and big-endian orders. A *nonzero* candidate is
within the arbitrary engineering range 1e-8 through 1e4 in magnitude.
Exact zeros, tiny, huge and nonfinite values are counted **separately**.

Two compelling but competing alignments, counting only **distinct
payload byte sequences** (not all repeated records):

| Variant | LE at offset 1, nonzero window / zeros | BE at offset 0, nonzero window / zeros |
|---|---:|---:|
| 0 (80 candidate lanes) | 34 / 31 | 30 / 22 |
| 1 (54 candidate lanes) | 24 / 17 | 20 / 12 |
| 2 (56 candidate lanes) | 9 / 28 | 7 / 20 |

Without removing repeated payloads, offset-1 LE yields nonzero
values 86/176, 40/78 and 13/72 for variants 0, 1, 2.
After deduplication the differences in nonzero candidate counts
between LE-offset-1 and BE-offset-0 are only **4, 4 and 2**.

Therefore the perceived float32 interpretation is **weak evidence**;
it does not independently establish the original numeric field
types or original game physics. Alternative byte orders also generate
plausible values. Byte repetition and abundant exact zeros strongly
affect the totals. All original payloads and numeric values remain
private.

## Reusable privacy-preserving source tools

The Python module at
src/heman_tools/physics_payload_dedup_controls.py does the following:

- Reuses strict Stage147 structural parsing and Stage148 opaque payload
  extraction without writing source bytes or per-file results.
- Evaluates **all four alignments and both byte orders**, reporting
  two independent tallies: all record occurrences and distinct entire
  payload patterns.
- Never counts exact zeros as positive support for a numeric field.
- Counts only the number of four-byte candidate lanes with any
  nonzero-in-window values or two distinct such values; it never
  reports source field offsets or original values.
- Retains permanent false flags for original physics, object-shape
  ownership, gameplay fidelity and automatic collision import.

Owner-local command:

    PYTHONPATH=src python -m heman_tools.physics_payload_dedup_controls \
      --ipa /secure/private/He-Man-v2.0.0.ipa \
      --out local_reports/physics_payload_dedup_controls.json

The optional JSON goes to ignored local_reports/ and exposes only
aggregate counts. Do not upload the IPA or original extracted game
assets to public CI, Actions artifacts or GitHub issues.

The public regression suite adds **22 wholly fictional** tests
covering repeated blocks, zero-exclusion, nonzero candidate diversity,
malformed UTF-16/variant frames, NaN/Inf, 8 endian/offset combinations,
duplicate ZIP names, symlinks and source-pack mismatch.

## Remaining blockers

- No independent evidence that any current field is really float32.
- No source coordinate-to-world transform or physics engine units.
- No confirmed per-level object-to-shape ownership or hitbox semantics.
- No Nintendo Switch runtime changes, original gameplay parity claim
  or physical Switch validation in this stage.

Next, seek **external to the blob** evidence such as independently
decoded resource references and original iOS gameplay traces, then
test whether numeric interpretations agree across both. Do not infer
game-rule semantics from float plausibility alone.
