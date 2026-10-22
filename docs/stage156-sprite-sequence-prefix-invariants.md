# Stage156 — five-word sequence prefix: invariants and resolution-specific exceptions

## Original owner-private iOS v2.0.0 evidence

This stage extends Stage155's strictly bounded and index-matched
`SpriteSeqData.wad` records, using only the owner's privately held
original IPA. No original WAD bytes, resource names, sprites, object
positions, sequence key strings or per-record offsets are copied into
GitHub, public CI or Actions artifacts.

There are **2,354** indexed sequence records: three have an empty
unknown candidate-count field and exactly a single terminal u32,
and the remaining **2,351** have a nonempty middle region. In each
nonempty region at least the first **20 bytes** exist, and can be
read consistently as five little-endian u32 bit patterns. The entire
record remains unparsed beyond that observed five-word prefix.

| Strict cross-resource observation | Original aggregate |
|---|---:|
| Nonempty candidate records with complete five-word prefix | **2,351 / 2,351** |
| First word identical in both resolution packs | **2,351 / 2,351** |
| First word exactly zero | **7 / 2,351** |
| Maximum observed first word (meaning unknown) | **17** |
| Second word exactly zero, both packs | **2,351 / 2,351** |
| Third word identical between both packs | **2,349 / 2,351** |
| Third word **different** between packs | **2 / 2,351** |
| Fourth word zero | **2,350 / 2,351** |
| Fifth word zero, both packs | **2,351 / 2,351** |
| Entire five-word prefix identical between packs | **2,349 / 2,351** |
| Records with additional opaque bytes after five words | **2,351 / 2,351** |

The **two third-word differences are not errors to normalize away**:
the original `screen-med` and `screen-xlarge` packs are known to
contain resolution-specific sprite WAD contents. Even where a field
*looks* like a stable value or a zero marker, its runtime meaning
must be established independently. A number may encode a source
specific reference, sprite option, version, position, padding,
duration or other untested data.

Stage156 does **not** assert that any of the five words are
frame counts, frame indices, frame durations, sprite dimensions,
animation flags, collider sizes, or renderer commands. In particular,
the stage does not identify a set of nested frame records, parse
animation timelines, or change the experimental Nintendo Switch NRO.

## Privacy-preserving validation

New source-only module:
`src/heman_tools/sprite_sequence_prefix_invariants.py`.

It reuses the strict Stage153 repository index, Stage154 indexed
record intervals and Stage155 candidate-count/trailing-u32 validation.
For each nonempty indexed sequence it:

1. Requires at least 20 payload bytes *before* the final u32.
2. Reads exactly five `<I` words in each source screen pack.
3. Validates the originally observed zero values of the second and
   fifth words while preserving the rare nonzero fourth-word value.
4. Checks cross-pack equality of first, second, fourth and fifth
   words. The third word is deliberately allowed to differ, with
   both equal and unequal occurrences counted.
5. Returns **only fixed-name aggregate counters**, and explicit
   `false` claims for actual source frame/physics interpretation.

Run against only the owner's private copy:

```sh
PYTHONPATH=src python -m heman_tools.sprite_sequence_prefix_invariants \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_sequence_prefix_invariants.json
```

The `local_reports/` folder is gitignored. No private record names,
per-file index entries, individual values, sprite pixels, original
byte slices or hashes are written.

The public regression suite includes **19 fictional-data tests**,
with explicit false-positive controls for cross-pack exceptions,
nonzero fourth words, reserved-zero deviations, manipulated record
headers, missing indexed data, duplicate ZIP members, symlinks,
private report redaction and full synthetic IPA integration.

## Gate for next research

Seek a repeated, bounded nested-item record format that consumes
every opaque byte between this fixed header and the terminal u32
**across all 2,351 nonempty sequences**. Testing candidate counts
against simple repeated fixed-size subrecords can help falsify
oversimplified layouts, but variable-length data and image references
must not be guessed into actual frame counts.

No original iOS playback/animation timing, player-state binding,
hitbox switching, image import or physical Nintendo Switch fidelity
has been established here.
