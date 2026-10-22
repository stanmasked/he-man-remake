# Stage154 — exact intervals and initial structural headers of indexed iOS sprite records

## Verified on the owner's private original iOS v2.0.0 IPA

Stage153 established three repository indexes with 3,599 entries and the
absolute WAD offsets for each entry. Stage154 used those offsets to
bound the record *payload spans* as the half-open interval from one
offset to the next, or to the end of the WAD for the final entry.

The intervals are strictly positive, bounded, disjoint, start at
byte zero, and cover **every byte of their respective original WAD**.
Both original screen packs use identical indexes and record lengths.
The original WAD data and images are never exported.

| Family | Original indexed spans | Min bytes | Max bytes | Whole spans byte-identical between screen packs |
|---|---:|---:|---:|---:|
| Sprite sequences | 2,354 | 50 | 18,979 | 197 |
| Sprite cut / sprite resource | 1,156 | 68 | 476 | 0 |
| Single frame | 89 | 52 | 136 | 0 |
| **Total** | **3,599** | | | **197** |

Thus a screen-resolution-specific WAD can contain different sprite
contents while its record names, offsets, and initial structural
header fields remain stable.

## Record headers, not animation timelines

### Sequence record (2,354 of 2,354 verified)

Immediately after the indexed UTF-16LE resource key is a little-endian
32-bit value. For the original iOS assets, its identical value in both
screen packs falls into one of three aggregate categories:

| Serialized 32-bit value category | Count |
|---|---:|
| Exactly zero | **1,689** |
| All bits set (0xFFFFFFFF) | **642** |
| Another 32-bit value | **23** |
| **Total** | **2,354** |

This is **an observed marker only**. In particular, all-bits-one does
not establish a signed sentinel or a missing-animation meaning.
The remaining bytes of each sequence record are **not parsed as
frames, timelines or poses**.

### Sprite cut record (1,156 of 1,156 verified)

Immediately after the indexed UTF-16LE resource key is **another
length-prefixed UTF-16LE string**. For all 1,156 entries, this string
is structurally valid, leaves subsequent record bytes, and agrees
between medium/extra-large WAD packs.

That second string's semantic role (texture, sheet, resource handle
or another key) is **not established**. No sprite rectangles,
coordinates, pixels or source image data have been decoded.

### Single-frame record (89 of 89 verified)

These WAD records begin with an independently valid length-prefixed
UTF-16LE string, equal between source screen packs, but **none of the
89 header strings equals the indexed repository key**. This confirms
that Stage153's direct key-at-offset rule must **not** be applied
unchanged to single-frame WAD records.

The relation between that leading text and the 89 repository keys
is not yet understood.

## Implementation

Added `src/heman_tools/sprite_wad_record_intervals.py`:

- Reuses strict Stage153 `.repo` parsing and existing bounded/private
  ZIP reader. Rejects resource-index duplicates, unsafe ZIP members,
  missing resource families, malformed keys and non-increasing offsets.
- Verifies **whole WAD interval coverage** with a conservative
  32,768-byte per-record budget, and identical interval lengths
  across resolution packs.
- For sequences, checks the next serialized `u32` value and its
  screen-pack agreement, counting only coarse marker categories.
- For sprite cuts, validates the second UTF-16 token and cross-pack
  equality, leaving remaining data uninterpreted.
- For single-frame records, validates the leading UTF-16 string
  **without** claiming it identifies the indexed resource.
- Reports **aggregate counters and unverified capability flags only**;
  no names, individual offsets, per-entry spans, original images,
  frame bodies or private file hashes are written.

Owner-local command:

```sh
PYTHONPATH=src python -m heman_tools.sprite_wad_record_intervals \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_wad_record_intervals.json
```

The report stays under gitignored `local_reports/`, and no original
WAD data or extracted sprite images enter public CI, the PR, releases,
or Actions artifacts.

The public regression suite uses **22 completely fictional** tests
for disjoint full-WAD intervals, three artificial sequence markers,
cut secondary tokens, single-frame alternative names, screen-specific
sprite bytes, index/header inconsistency, malformed UTF-16, oversized
records, duplicate ZIP members, selected symlinks and report redaction.

## Remaining evidence gates

The following are still **unverified**:

1. Original animation frame count, playback duration and frame order.
2. Sprite sheet/cut coordinates and pixel encoding.
3. How `LevelObject.state` (e.g. `idle`) maps to a specific sprite
   sequence or animation command.
4. Whether the game changes any collider in response to its animation.
5. Whether the synthetic Switch NRO reproduces the original iOS
   player movement, collision behavior or rendering.

Next: exploit indexed **record span** boundaries to test independently
falsifiable, bounded sequence-frame and sprite-cut structures, always
validating complete record consumption and using synthetic public CI.
Do not equate the serialized marker to time or frame count yet.
