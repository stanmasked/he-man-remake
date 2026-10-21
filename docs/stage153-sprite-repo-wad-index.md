# Stage153 — verified sprite repository index to WAD record offsets

## Original iOS v2.0.0, read-only private evidence

The owner's original He-Man iOS archive contains a common, bounded
repository index format in three previously opaque metadata files:

```text
[u16 UTF16 repository label]
[u16 zero marker]
[u32 entry count]
repeat entry count:
  [u16 UTF16 resource key]
  [u32 zero marker]
  [u16 UTF16 referenced relative WAD path]
  [u32 little-endian offset into WAD]
EOF
```

Unlike Stage152's whole-file lexical scan, Stage153 verifies a
**specific serialized lookup path**: resource key → WAD file path →
absolute WAD byte offset, using a strictly decoded record count and
file-end check.

| Source index | Entries | Indexed WAD | Result in both resolution packs |
|---|---:|---|---|
| `SpriteSeqData.repo` | **2,354** | `SpriteSeqData.wad` | At all 2,354 offsets the length-prefixed UTF-16 **same full key** starts the record |
| `SpriteCutData.repo` | **1,156** | `SpriteResData.wad` | At all 1,156 offsets the length-prefixed UTF-16 **same full key** starts the record |
| `SingleFrameSpriteData.repo` | **89** | `SingleFrameSpriteData.wad` | All 89 offsets are valid, but the WAD record header uses another name/reference scheme |
| **Total** | **3,599** | | **3,510** independently confirmed key-at-offset WAD headers per pack |

Across all three indexes, the archive-contained entry stream consumes
its repository file exactly. The observed 32-bit markers are zero for
every entry. Names and numeric offsets are strictly increasing and
unique within each repository. All first offsets are zero.

The three `.repo` files are **byte-identical** between the original
`screen-med` and `screen-xlarge` directories. Their WAD files are
the **same lengths but have different contents**, including:

| WAD family | Size per screen pack | Different bytes at matching offsets |
|---|---:|---:|
| Sprite sequence | 2,106,313 bytes | 29,638 |
| Sprite resource / cut | 171,858 bytes | 7,882 |
| Single-frame sprite | 7,502 bytes | 348 |

**The 89 single-frame entries are not falsely promoted to confirmed
name-at-offset mappings.** Their offsets are valid in both archives,
but the leading token at these positions does not equal the index
key under the sequence/cut interpretation. This requires a separate
reader rather than assuming that all WAD types share one record body.

## Implementation

The public **asset-free source** module
`src/heman_tools/sprite_repo_wad_index.py` reconstructs this index
envelope, requiring finite member sizes, strict UTF-16, expected
repository name, zero markers, unique keys, increasing offsets, exact
EOF, and source-pack parity for `.repo` metadata. For sequence/cut
WADs it requires exact full key equality at **every** indexed offset
in **both** resolution packs.

For single-frame WAD it validates only offsets and explicitly labels
the distinct header format as unknown.

Owner-private command:

```sh
PYTHONPATH=src python -m heman_tools.sprite_repo_wad_index \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_repo_wad_index.json
```

The report contains **aggregate counters, file sizes, byte-difference
counts and static capability flags only**. All original sprite keys,
locations, frame data, archives, per-resource offset maps, decoded
pixels and raw bytes remain on the owner's system. The
`local_reports/` directory stays ignored by git.

Public CI uses **21 entirely fictional regression tests** to check
valid and invalid repository headers, entries, duplicate keys, path
references, truncated string fields, offset uniqueness/bounds,
UTF-16 encoding, WAD header equality and inequality, screen-pack
differences, duplicate ZIP entries and selected symlink rejection.
The original IPA is never uploaded to GitHub.

## Remaining compatibility barriers

1. Individual WAD **record bodies**, animation frames and timings
   are not decoded.
2. Single-frame WAD record headers require their own format study.
3. Level-object `idle` or another source state has not been mapped
   to a concrete sprite index key in the original game engine.
4. Runtime animation changes and associated hitbox switching have not
   been observed or proven.
5. No Switch graphical/gameplay parity or physical hardware proof
   follows from successful parsing of this index.

Next: study individual WAD record bounds **using adjacent index
offsets**, privately, without extracting sprites to public CI. Then
identify a complete frame/timing structure with falsifiable checks
on every indexed record before attempting animation-driven collider
updates.
