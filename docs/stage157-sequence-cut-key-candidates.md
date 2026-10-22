# Stage157 — first independent sequence-to-sprite-cut name candidates

## Owner-private original iOS v2.0.0 evidence

Previous stages established that all **2,354** sequence WAD records
have exact index boundaries, and **2,351** have nonzero unknown
candidate counts followed by at least five `u32` words. Stage157
investigates the opaque bytes **after those 20 bytes**.

At a constant offset of **13 additional bytes** after the five-word
prefix, a valid bounded `[u16 UTF-16 code-unit count][UTF-16LE name]`
candidate occurs in **2,344 of 2,351** nonempty original sequence
records. The name is identical across `screen-med` and
`screen-xlarge` packs for every such candidate.

Most importantly, **2,335 of those 2,344 names match exact,
independently parsed keys of `SpriteCutData.repo`**. That index
is a separate resource family with its own previously verified
record counts and WAD references.

| Category at offset +13 | Original aggregate |
|---|---:|
| Nonempty sequence records examined | **2,351** |
| Valid printable length-prefixed UTF-16 candidate | **2,344** |
| Candidate also found as exact sprite-cut index key | **2,335** |
| Valid candidate not found in sprite-cut index | **9** |
| Candidate also equals a source sprite-sequence index key | **91** |
| Candidate belongs to both sequence and cut key indexes | **91** |
| Empty UTF-16 names | **6** |
| Too short even for candidate length field | **1** |
| Other malformed candidate strings | **0** |

The above categories are based on real source data, but **do not**
establish nested frame boundaries. In particular, the 13 preceding
opaque bytes have no verified field types. An exact cross-resource
name is a strong *reference candidate*, not proof that the engine
loads and renders the cut resource at that point of playback.

### Predeclared negative-offset controls

This offset is substantially more specific than searching for an
arbitrary string anywhere inside an archive. Stage157 tests a fixed
set of alternative relative byte offsets without optimizing the
offset per record:

| Relative position after five words | Printable UTF-16 candidates | Exact cut-index key matches |
|---:|---:|---:|
| 0, 4, 8, 12, 14, 16, 20, 24 or 32 | **0** | **0** |
| **13** | **2,344** | **2,335** |

These controls were run against the same 2,351 sequence records.
They strengthen the evidence for a reproducible record field but
cannot tell us the nested record size or the role of the 13 bytes.

The original source has two exceptional sequences whose *earlier*
five-word prefix differs across screen packs; the Stage156 validator
preserves those differences. Stage157 requires exact string parity
only at its predeclared +13 candidate position. Arbitrary alternative
control offsets may contain resolution-specific opaque data and
are not falsely required to decode identically between packs.

## Public implementation and privacy guardrails

Added `src/heman_tools/sprite_sequence_cut_name_candidates.py`.

- Reuses strict Stage153 sprite `.repo` parser, Stage154 bounded WAD
  intervals, Stage155 sequence field and Stage156 five-word validation.
- Loads the `SpriteCutData.repo` index independently, validates
  resolution-pack byte identity, and matches only **complete token
  strings** against its exact resource keys.
- Counts empty, short, malformed and valid-unmatched cases
  separately; never rewrites missing matches into an invented sprite.
- Tests a fixed, explicit set of negative control offsets.
- Emits **only aggregate counts and fixed capability flags**;
  no original strings, individual record offsets, image bytes,
  animation frames, source geometry or file hashes are exposed.

Run only with the privately owned original IPA:

```sh
PYTHONPATH=src python -m heman_tools.sprite_sequence_cut_name_candidates \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_sequence_cut_name_candidates.json
```

The optional JSON is stored under gitignored `local_reports/`.
Never upload the IPA, source sprites or generated original-game
geometry to the public GitHub repository.

The synthetic-only suite includes **18 tests** for full and partial
index matches, exact and alternative offsets, length-prefixed UTF-16
validity, empty and truncated tokens, same-length screen-specific
body changes, mismatching candidate names, archive parity, invalid
index fields, duplicate ZIP entries, symlinks and report redaction.

## Remaining evidence threshold

No original frame count, duration, sprite-cut selection chronology,
animation state dispatch, on-screen character movement, collision
hitbox ownership or physical Nintendo Switch gameplay parity is
yet established. Next study the structure of the **remaining bytes**
and determine whether repeated nested items consume the entire
record in a way consistent with the unknown count field. Demand
exact EOF and independent source resource matches for any proposed
frame/timing schema before importing sprites into the Switch test.
