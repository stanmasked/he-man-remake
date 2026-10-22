# Stage158 — falsify a repeated nested sprite-cut name layout

## Real original source (owner-private, read-only)

Stage157 found the first candidate `SpriteCutData.repo` key at a
stable byte position inside most nonempty original `SpriteSeqData.wad`
records. Stage158 tests whether the earlier UNKNOWN u32 count can
correspond to repeated instances of a *candidate* cut-key-bearing
inner record, with **exact end-of-record consumption**.

This is a **restricted, unverified grammar**, not a declaration of
the original frame serializer:

```text
Sequence: [previous validated header with unknown candidate count]
          [five previous u32 fields]
          [13 uninterpreted bytes]
          [u16-length-prefixed UTF-16 candidate cut name]
          repeated (count - 1) times:
              [64 + 82*k uninterpreted bytes]
              [12 OR 33 uninterpreted bytes]
              [u16-length-prefixed UTF-16 candidate cut name]
          [64 + 82*k uninterpreted bytes]
          [last u32 already validated by Stage155]
```

Here `0 <= k <= 20` for each spacing. A candidate name must be an
**exact key in the independently parsed `SpriteCutData.repo`**.
These choices are bounded on purpose. Names and opaque byte spans
stay private. A dynamic-programming search counts complete paths but
**saturates at 2**; it never picks one of multiple matching
segmentations. A candidate is accepted only if the declared number
of names is parsed and the cursor ends **exactly at the existing
record boundary before the final u32**.

### Source-private original census

Read-only tested against all **2,351** original iOS v2.0.0 source
sequence records with a nonzero unknown count, in **both**
`screen-med` and `screen-xlarge`. The classifications are equal
between packs:

| Predeclared model | No initial matching cut key | First key matches, but no complete parse | Exactly one parse | Ambiguous (2+) |
|---|---:|---:|---:|---:|
| **Base 64, stride 82** | **16** | **677** | **1,628** | **30** |
| Base 63, stride 82 | 16 | 2,335 | 0 | 0 |
| Base 65, stride 82 | 16 | 2,335 | 0 | 0 |
| Base 64, stride 80 | 16 | 762 | 1,566 | 7 |
| Base 64, stride 84 | 16 | 767 | 1,558 | 10 |

The 16 no-initial-key cases correspond to previously identified
Stage157 exceptions. The model base of 64 bytes is strongly
constrained by exact EOF in this test; moving it by **one byte
eliminates all complete parses**. In contrast, the difference
between stride 82 and alternatives 80/84 is **not large enough
to prove that the real engine uses an 82-byte subrecord**. Several
candidate paths occur only because opaque bytes were allowed to
vary by the predeclared integer `k`.

Among the original one-count records whose first candidate name
matches the cut index, residual lengths after that name often equal
**64** bytes (708 observations), with some **146**-byte and
**228**-byte residuals, which motivated the `64 + 82*k` hypothesis.
Such remainders are still simply source byte-structure evidence, not
rendered frame duration or keyframe counts.

**Critical falsification result:** the main grammar fails on
**677** additional records despite a matching initial cut key.
It leaves **30** more ambiguous. Therefore it is **not a
universal or independently verified nested animation format**.
The user’s game resource reader must *not* select or import the
1,628 candidate segmentations as authoritative frames.

## Implementation, safeguards, and tests

New `src/heman_tools/sprite_sequence_nested_grammar.py`:
- Reuses Stage153's strict asset index, Stage154's exact WAD
  intervals, Stage155's validated count/last-word, Stage156's
  five-u32 prefix and Stage157's independently indexed cut names.
- Uses memoized bounded search and aggregate return values
  `-1/0/1/2+` for missing first name, no path, unique path or
  ambiguity. Does not materialize source-specific output paths.
- Applies predeclared shifted-base and shifted-stride controls and
  verifies both source screen packs produce the same counts.
- Does **not** decode frame indices, playback timing, sprite pixels,
  hitboxes or actual actor-state→sequence ownership.

Run only with the original IPA stored privately:

```sh
PYTHONPATH=src python -m heman_tools.sprite_sequence_nested_grammar \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_sequence_nested_grammar.json
```

The output is aggregate only, and `local_reports/` is gitignored.
No original commercial game files, WADs, sprites, resource keys,
raw offsets, opaque blocks, collision geometry or individual assets
enter the public repository or GitHub Actions.

Public regression tests use fictional sequence/cut repositories and
fake WADs, including a deliberately ambiguous two-parse case,
truncated/extra-byte rejection, false initial names, altered
screen-pack opaque contents, mismatching nested name controls,
duplicate ZIP members, symlinks and aggregate report redaction.

## Next source research gate

A useful advance must *explain rather than discard* the 677 failures
and 30 ambiguities with additional **independent format evidence**.
Inspect the different name kinds and prefixes in these exceptions
and seek a record grammar that consumes all source records without
arbitrary data-selection rules. Only then investigate timings and
concrete animation playback. The original independently authored
Switch test NRO is unchanged here.
