# Stage167 — verified native SpriteSequence / SpriteFrame / Symbol format

**Evidence level:** independent native ARMv7 executable control flow,
followed by exact record parsing of the owner-held iOS v2.0.0 IPA in
private local analysis. This supersedes the earlier speculative
"unknown candidate count" and "82-byte frame" interpretations.

No original executable, disassembly listing, source asset, proprietary
string/key, graphic, per-record data or IPA copy belongs in public GitHub.

## Confirmed nested binary format

The original loader calls `SpriteSequence::fileIn` and uses the
signed 32-bit frame count to allocate/initialize and read frames. Each
frame invokes `SpriteFrame::fileIn`, which in turn uses a signed 32-bit
symbol count to read `Symbol::fileIn` records.

| Layer | Serialized fields |
|---|---|
| Sequence | Length-prefixed UTF-16LE identifier; three signed 32-bit fields (first returned by getLoop, second is frame count) |
| Frame | Four signed 32-bit values; one byte read by original `read_bool`; signed 32-bit symbol count |
| Symbol | Two signed 32-bit values; length-prefixed UTF-16LE name; four signed 32-bit values; six 32-bit floats; four signed 32-bit values; three further signed 32-bit values |

The second signed 32-bit value of each frame is exposed by the
original `SpriteFrame::getTime`. The original
`SpriteSequence::getAnimationTime` sums those per-frame values.
**Real-time units have not been calibrated** against captured original
playback. Frame count and frame time *field identities* are confirmed;
on-device playback timing remains a separate gate.

The serialized frame header is **21 bytes**; a serialized symbol
consumes **76 fixed scalar bytes plus a length-prefixed UTF-16LE name**.
A two-code-unit name occupies 6 bytes, producing an **82-byte symbol**.
Therefore 82 is not the size of a frame. Similarly, distances between
consecutive visible names can include the remainder of the preceding
symbol, another symbol's two leading integers and intervening 21-byte
frame headers.

The earlier "final u32" is **not the loop flag**: for the common
nonempty records it is the last integer of the last symbol. The loop
field sits at the start of the sequence header and is accessible
through the game's getter.

## Strict and safe parser

`src/heman_tools/sprite_sequence_native_loader_structure.py`:

- Reads exactly the above format, with bounded counts, strict UTF-16
  handling and **exact end-of-record consumption**.
- Independently validates paired `.repo` indexes and source WADs,
  reusing the Stage154 structural controls.
- Counts frames, symbols, named cut-registry references, and unindexed
  short names anonymously. Unindexed names are **not silently erased**:
  the original loader reads them; whether they are special effects,
  internal markers or otherwise has not yet been established.
- Separately compares frame counts, symbol counts, symbol identifiers
  and generic numerical frame header equality across source resolution
  packs.
- Does not export source strings, raw integer fields, per-record
  counts, paths or binary data. All named parse objects remain inside
  the private process.

Independent owner-only direct reconstruction found exactly **2,354
indexed sequences per resolution**, **7,889 frames per resolution** and
**14,971 symbols per resolution** with **zero strict parsing failures**.
Within one resolution pack, 13,432 symbol names were independently
present in the indexed cut registry; 1,539 were absent (1,538 of the
absent names had exactly two code units). Those findings are summary
counts only, not original asset payloads.

The frame-count and symbol-name/counter shapes match between the two
packs. Two sequence records have differing numeric frame fields, which
are recorded as source-resolution data differences rather than
mistaken for parse failures.

## Test gates and original-asset protection

Synthetic-only regression:
`tests/test_sprite_sequence_native_loader_structure.py`.
This includes invented frames and names, zero-frame and zero-symbol
cases, 82-byte two-unit symbols, frame duration field location,
paired screen differences, corrupt name/size/count cases, strict EOF,
duplicates, selected symlinks and output redaction.

Private owner-only command:

```sh
PYTHONPATH=src python -m heman_tools.sprite_sequence_native_loader_structure \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_sequence_native_loader_structure.json
```

Only the owner should execute this with the original IPA. The private
`local_reports/` directory is ignored by Git. **Never upload the IPA,
any extracted sprite WAD, executable, reconstructed source art or
private per-record data to public GitHub/CI.**

## Next research gate

The native format supplies verified frame and symbol boundaries, but
not their rendered visual appearances or exact real-time playback
units. Next verify frame duration units, loop policy, symbol texture
lookup and transforms, and actor-state/hitbox attachment using
independent original runtime evidence before asset integration.

The synthetic Switch NRO and `main` remain unchanged.
