# Stage161 — compare opaque single-sprite suffixes across iOS screen packs

**Status:** source-only diagnostic; no original IPA execution claimed here.
This branch is stacked on Stage160 / Draft PR #160. The original iOS
v2.0.0 IPA remains owner-private; Switch NRO and gameplay code unchanged.

## Why this comparison matters

Stage159 showed **708/708** indexed count-one records with prefix first
u32 = 1 have a 64-byte residual after the first independently indexed
cut key; known count-one records with first u32 not equal to 1 have
other residual lengths, including 162 and 576 bytes.

Stage160 tests the *relationship* between in-memory first-u32 values
and residual-length consistency. Stage161 asks a different question:
**do those opaque residual bytes remain identical between the two
original iOS resolution-specific source packs?**

Matching bytes might be shared metadata or reused content; changing
bytes might be resolution-specific data or serialization differences.
Neither observation alone identifies sprite pixels, frame boundaries,
durations, loop flags, animation transitions or gameplay rules.

## The exact comparison boundary

1. Reuse Stage159 strict validation of paired `.repo` and `.wad`
   indexes, source cut registry, name evidence, candidate-count values
   and original record intervals.
2. Restrict comparisons to records with unknown candidate count **1**.
3. Require the same exact cut key in both screen packs, with that key
   independently present in `SpriteCutData.repo`.
4. Compare only bytes **after the known first key** and **before the
   separately observed terminal u32**.
5. Separate `first_u32_one` and `first_u32_other`, and the coarse
   Stage159 suffix categories `64`, `162`, `576`, `other`.
   If the first cut key is unknown, count the record but do not
   compare any opaque bytes.
6. Publish only aggregate counts in coarse categories: records,
   compared pairs, byte-identical, 1–4 differing byte positions,
   5–16, 17–64 and 65+. No changed positions or original bytes,
   exact suffix lengths in the `other` category, names, raw header
   values or record-level data leave the private runtime.
7. Require all Stage161 motif totals to exactly match Stage159 totals.

The comparison is bytewise; there is **no proposed nested frame
layout**, no pixel decode and no serializer semantics imported into
the NRO. Both packs' equality/difference observations remain source
facts only.

## Code and synthetic safety tests

- Analyzer:
  `src/heman_tools/sprite_sequence_suffix_screen_parity.py`
- Fake-only tests:
  `tests/test_sprite_sequence_suffix_screen_parity.py`
- Tests cover zero/1/4/5/17/65 byte differences, word1 != 1,
  unknown cut names, bad paired headers, output redaction,
  synthetic ZIP loading, duplicate ZIP members and selected symlinks.

To run privately on an authorized owner-held IPA:

```sh
PYTHONPATH=src python -m heman_tools.sprite_sequence_suffix_screen_parity \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_sequence_suffix_screen_parity.json
```

The report remains ignored under `local_reports/`. Never upload
original IPA, extracted resources or private source report to GitHub.
This PR does not claim original results, animation recovery,
hardware performance or real-game parity.

## Next decision

Once the private report is available, compare the degree of
cross-screen suffix equality by firstword group and motif. Seek
*independent* source-format or runtime evidence before interpreting
byte differences as image content or using them as animation data.
