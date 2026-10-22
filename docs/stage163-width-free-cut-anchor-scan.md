# Stage163 — width-free secondary sprite-cut lexical anchors

**Status:** source-only, owner-private diagnostic. No original IPA run is
claimed in this PR. No Switch NRO changes.

## Motivation

Stage158 tried a fixed terminal-64 / opaque-82 stride hypothesis and
found 677 no-fit sequences. Stage159 found **649** of those have first
prefix u32 different from 1. Stages160–162 explore header groupings,
opaque suffix lengths and cross-screen differences. A major unresolved
question is whether **additional independently indexed SpriteCutData
names** appear at all inside the same records *without assuming the
Stage158 widths*.

This stage uses a deliberately weaker source observation: a candidate
anchor is an **exact** serialized

    [u16 code-unit count][bounded printable UTF-16LE name]

whose name is independently registered by SpriteCutData.repo. Scan the
record bytewise after the initial previously established known cut name
and stop before the already validated final u32. Never assume any
particular gap, block size, frame interval, renderer or duration.

This is a **lexical inventory, not a parser**. Such a token could be
incidental data or part of an unrelated nested structure; even several
matches do not prove actual frames.

## Controls

- Reuse the Stage159 strict paired source package verification:
  complete WAD intervals, real repository keys, candidate-count and
  five-word header constraints, both screen packs, safe ZIP handling.
- Build the reference token registry from the independently validated
  sprite-cut index, not the sequence body.
- Match a **length prefix and all UTF-16 bytes**, not just a substring
  of an original cut name.
- Scan every byte offset without using an assumed 64/82 stride; use
  greedy non-overlapping matches and cap each record at 512 hits.
- Group by firstword=1 vs other and the independent declared-count
  categories (1, 2, 3–4, 5–10, 11+).
- Report only coarse categories: first key missing, a count-one record
  with no/some later indexed tokens, or a multi-count record with
  zero, fewer, exactly the expected number, or more secondary matches
  than `declared_count - 1`.
- Compare complete internal anchor position+name lists between
  screen packs, but publish only **match/mismatch counts**. Different
  screen-pack opaque content is an observation, not automatically a
  failure.
- Check record and missing-first-key totals against the independent
  Stage159 summary. Reject malformed input rather than guessing.

The expected number of secondary names is only a **hypothesis control**:
the still-unknown candidate count has *not* been proven to count actual
frames or child records. A matched count never promotes lexical tokens
to source animation.

## Code and tests

- `src/heman_tools/sprite_sequence_cut_anchor_scan.py`
- `tests/test_sprite_sequence_cut_anchor_scan.py`
- **20** artificial-only cases for bytewise scanning, prefix membership,
  forged token controls, count groupings, screen-pack differences,
  synthetic IPA integration, bound checks, redaction, duplicates and
  unsafe ZIP symlinks.

Run only in an owner's controlled local environment:

```sh
PYTHONPATH=src python -m heman_tools.sprite_sequence_cut_anchor_scan \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_sequence_cut_anchor_scan.json
```

The `local_reports/` directory is ignored. Never upload the IPA,
original art, per-record labels, raw numeric field values, offsets,
bytes or a private report to a public CI system.

## Decision after a future private run

A finding of zero later indexed cut names in many multi-count records
would falsify any simple interpretation that every counted child is
represented by one plain indexed cut token. Multiple anchors in a
count-one record would also disprove a naive one-to-one lexical
interpretation. A candidate name's position remains uncertain without
an independent serializer/runtime witness.

Frame boundaries, durations, transitions and animation-triggered
colliders remain unknown. The synthetic Switch NRO remains unchanged.
