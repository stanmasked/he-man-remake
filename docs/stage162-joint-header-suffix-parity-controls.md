# Stage162 — joint firstword/suffix cross-resolution controls

**Purpose:** falsify over-strong interpretations of the *first* little-endian
`u32` in the independently observed five-word header of iOS v2.0.0
`SpriteSeqData` records. No original animation decoder is claimed.

Stage159 showed a strong association between word=1 and a 64-byte
suffix following a known indexed sprite-cut key for count-one records.
Stage160 tested groupwise length consistency within other firstword
values; Stage161 compared opaque suffix bytes across the two original
resolution packs. **Stage162 tests the interaction** between those
two independent questions, without revealing firstword values,
individual record information or opaque suffix bytes.

## Four possible source structures

For a firstword value different from 1, consider only those records
with an independently indexed first cut key and unknown count=1.
Require at least **two** such records with the same private word value
to classify an eligible group:

| Lengths within same firstword group | Two screen packs | Interpretation |
|---|---|---|
| All exact suffix lengths equal | All suffixes identical | Compatible with a common size, not proof of a frame type |
| All exact suffix lengths equal | Any suffix changes | Common serialized length with pack-specific bytes |
| Some exact suffix lengths differ | All suffixes identical | Refutes that firstword alone uniquely specifies suffix length |
| Some exact suffix lengths differ | Any suffix changes | Same refutation, with additional resolution-pack variation |

A header value occurring in only one known single-candidate record is
**not** evidence of fixed size. Unknown initial cut tokens are excluded
from length claims and retained in upstream source census.

Two additional *counts only* controls distinguish repeated firstword
groups containing multiple **coarse** length motifs (64, 162, 576,
other) and those containing at least two different exact residual
lengths within the `other_suffix` motif. The latter catches
variation hidden by a broad length bucket without exporting values.

## Independent validation gates

The implementation:
- Runs Stage160 and Stage161 strict summaries on the same paired source
  inputs. These transitively reuse Stage159, its independently indexed
  sprite-cut registry and strict original screen-pack checks.
- Requires joint eligible-group counts and the uniform/variable
  partition to match Stage160.
- Requires independently counted known non-1 single-suffix comparisons
  and *identical* suffix counts to match Stage161.
- Rejects missing paired files, unexpected prefix differences,
  malformed indexes, duplicate archive members and unsafe ZIP symlinks.
- Returns **only anonymous aggregate totals**; in-memory u32 values,
  record names, exact suffix lengths, bytes, coordinates, offsets,
  pixel content and positions never enter a report.

Source tool:
`src/heman_tools/sprite_sequence_joint_header_suffix_controls.py`

Synthetic-only regression:
`tests/test_sprite_sequence_joint_header_suffix_controls.py`

Run solely against a private authorized local IPA copy:

```sh
PYTHONPATH=src python -m heman_tools.sprite_sequence_joint_header_suffix_controls \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_sequence_joint_header_suffix_controls.json
```

The report is ignored under `local_reports/`. No original source
assets or private reports are allowed in public GitHub/CI.

## What remains unknown

No original IPA result is claimed at this stage. The diagnostic is
prepared for a private source run, but the owner IPA was not available
in this session. Even a strong statistical relationship cannot
identify serializer type, frame count, frame duration, playback
sequence, original collision bindings or physical Switch parity.
Do not import speculative animation slices into the Switch NRO.

**Next gate:** interpret the *private* four-cell census. If any
variable-length group occurs, reject the assumption that firstword
alone determines exact nested-record length. Then seek independent
source or runtime evidence to identify frame fields. Until then the
NRO remains a synthetic gameplay prototype.
