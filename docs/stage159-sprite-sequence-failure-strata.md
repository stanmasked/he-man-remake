# Stage159 — explain failure concentration in hypothetical sprite records

## Owner-private observations

Examined all **2,351** nonzero-count original sprite sequences in
the owner's original iOS v2.0.0 IPA read-only. Both resolution packs
produce identical aggregate results. This is not an original frame or
animation playback decoder.

### Five-word prefix first-u32 control

| First u32 | Missing first indexed cut key | No complete grammar path | Exactly one path | Ambiguous 2+ | Total |
|---|---:|---:|---:|---:|---:|
| **1** | 9 | **28** | **1,554** | 4 | 1,595 |
| Other | 7 | **649** | **74** | 26 | 756 |
| **All** | **16** | **677** | **1,628** | **30** | **2,351** |

Thus **649 of the 677 Stage158 failures** are in the first-word-not-1
subfamily, even though the old grammar had one shared record layout.
This is evidence of structural heterogeneity, **not** proof that the
u32 denotes a frame count, sprite type, timing or any game rule.

### Control by unknown candidate count

| Count group | Missing cut key | No complete path | Unique path | Ambiguous |
|---|---:|---:|---:|---:|
| 1 | 2 | 199 | 730 | 0 |
| 2 | 4 | 45 | 149 | 0 |
| 3–4 | 0 | 223 | 452 | 6 |
| 5–10 | 10 | 178 | 264 | 18 |
| 11+ | 0 | 32 | 33 | 6 |

### Independently measurable one-candidate record suffix

Of 931 sequences with an unknown candidate count of 1, two have no
initial cut-index name match. Among the **929** with an exact known
source-cut key, count opaque bytes between the end of that name and
the already validated last u32:

| Prefix first word | Known first cut keys | Remaining 64 bytes | 162 bytes | 576 bytes | Other |
|---|---:|---:|---:|---:|---:|
| Exactly **1** | **708** | **708** | 0 | 0 | 0 |
| Other | **221** | 0 | **40** | **67** | **114** |

Each first-word category also has one missing first name.

**708/708** is a strong conditional structural association. The
64-byte terminal segment is clearly not a universal size for all
source records. The other 162/576-byte residual motifs are real
aggregate observations only; no original semantic role is claimed.

## Implementation

Added source-only module
src/heman_tools/sprite_sequence_failure_strata.py. It reuses the
strict Stage153–157 index and candidate-name validations and
Stage158's bounded exact-EOF hypothesis. It counts grammar outcomes
by first-word and coarse unknown-count groups and checks the
single-candidate residual motifs. Aggregate comparisons must match
between both original screen packs.

All original file names, record values, byte arrays, sprites,
per-resource offsets and hashes remain private. Owner-only reports
are written to ignored local_reports/:

    PYTHONPATH=src python -m heman_tools.sprite_sequence_failure_strata --ipa /secure/private/He-Man-v2.0.0.ipa --out local_reports/sprite_sequence_failure_strata.json

Public CI uses **15 wholly fabricated tests**. These cover group
accounting, altered first words, residual motif comparisons, absent
cut names, archive duplication, selected symlinks, resolution-pack
divergence and report redaction.

## Next decisions

Do not pick a hypothetical nested segmentation as original game
frames. The first-word-based separation now provides a targeted way
to investigate the **649** otherwise unexplained failures without
broadening an already underconstrained byte model. Original frame
timing, actor-state bindings, collision ownership and hardware
Switch parity are all unverified. The synthetic NRO is unchanged.
