# Stage155 — unknown u32 count and ending-word controls in iOS sprite sequences

## Read-only analysis of the owner's original iOS v2.0.0 archive

Stage153 decoded the sprite repository index and Stage154 bounded all
2,354 sequence records in `SpriteSeqData.wad`. This stage compares
the bytes immediately following each indexed UTF-16 sequence key in
**both** original resolution packs.

Observed record prefix:

```text
[u16-length UTF-16LE indexed sequence key]
[u32 marker of unknown meaning]         — Stage154
[u32 candidate count of unknown meaning] — Stage155
[opaque sequence contents]
[u32 ending field of unknown meaning]    — Stage155
```

No candidate field is identified as a frame count, duration, playback
speed, loop mode, collision hitbox or original game engine enum.
The opaque middle contents have **not** been parsed as frames.

### Private, aggregate evidence

| Original source check | Aggregate |
|---|---:|
| Total indexed sequence records, checked in both packs | **2,354** |
| Candidate count = 0 | **3** |
| Candidate count = 1 | **931** |
| Candidate count = 2–4 | **879** |
| Candidate count = 5–10 | **470** |
| Candidate count = 11–45 | **71** |
| Candidate count above 45 | **0** |
| Maximum observed candidate count | **45** |
| Unknown trailing `u32` = 0 | **2,296** |
| Unknown trailing `u32` = 1 | **58** |
| Matching candidate-count/marker fields in both packs | **2,354 / 2,354** |
| Matching final `u32` in both packs | **2,354 / 2,354** |

All three zero-count sequences consist of a single four-byte zero
following their candidate count. The corresponding records still have
the valid full index-key envelope and a Stage154-verified interval.

The 32-bit word immediately following the candidate count is also
equal between both packs for all 2,354 records; a count of one or
more can still have extensive variable-length bytes after it.
The logical relationship between that count and any individual
frames, sprites or texture references is **unverified**.

These are independently repeatable *byte-structure* findings, not
evidence that the synthetic Nintendo Switch NRO now plays original
iOS animations.

## Public implementation

`src/heman_tools/sprite_sequence_header_controls.py` reuses the
existing strict Stage153 index and Stage154 WAD interval validators.
It compares the first 32-bit fields, the first following 32-bit word
and the last 32-bit word across both resolution packs; enforces
in-bounds record size, a conservative maximum candidate-count guard,
the observed zero-count minimal-record structure and a coarse 0/1
ending-field category.

Owner-private audit only:

```sh
PYTHONPATH=src python -m heman_tools.sprite_sequence_header_controls \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_sequence_header_controls.json
```

The JSON contains **aggregate counters and explicit unverified
capability flags only**. The `local_reports/` directory is ignored
by Git, and public CI contains only fictional `.repo` and `.wad`
records.

The synthetic suite tests all proposed buckets, screen-specific
body bytes, mismatched markers/counts/trailing words, excessive
candidate values, malformed record lengths, bad index keys,
duplicate ZIP entries, unsafe ZIP symlinks and report redaction.

## Next source-evidence gate

Investigate the structure of sequence contents *after* the candidate
count, as complete bounded records. A candidate framing model should
consume **all** nested contents exactly and remain consistent across
both original screen packs before identifying the count as the true
number of animation frames or inferring any frame timing.

Until independent runtime or asset-reference evidence is available,
the original texture/frame decoder, actor-specific animation states,
hitbox switching and gameplay physics all remain **unverified**.
