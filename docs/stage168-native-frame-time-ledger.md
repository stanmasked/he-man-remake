# Stage168 — native SpriteFrame time ledger and source-resolution audit

**Research stage.** Stage167 established the genuine binary loader's
`SpriteSequence` → `SpriteFrame` → `Symbol` structure and strictly
consumed all original indexed sequence records. Stage168 isolates the
**second signed 32-bit frame header value**, returned by native
`SpriteFrame::getTime`, and tests the corresponding accumulation
performed by native `SpriteSequence::getAnimationTime`.

The **units of the native time value remain uncalibrated**. A source
value of 100 must not be interpreted as 100 milliseconds until the
original runtime's clock/tick conversion has been independently shown.

## Source-private checks

- Read each original sequence using the exact Stage167 nested loader;
  reject malformed strings, counts, record lengths, indexes or archives.
- Group *individual* frame time values into six coarse categories:
  negative, zero, 1–9, 10–99, 100–999 and 1,000+.
- Sum signed frame time fields per sequence using an unbounded host
  accumulator. Report whether the sum would exceed signed 32-bit
  bounds; **do not emulate wraparound** or discard negative/zero frames.
- Preserve anonymous sign categories for the native loop and third
  sequence header values, without inferring looping semantics.
- Count zero-duration/negative-duration records and sequences with
  no frames, and separately retain noncanonical read-bool bytes.
- Compare frame time values, native boolean bytes and total time
  separately across both original resolution packs.
- Reconcile sequence/frame/empty totals with the independent Stage167
  structural census. Emit only aggregate counts: no individual
  sequence, source name, raw value, offset or binary content is exported.

## Private owner-source evidence (independent verification)

An owner-private independent loader-order script read both resolution
packs of the original authorized IPA and reported, for one resolution:

- 2,354 indexed sequences and 7,889 frame time values
- 15 time values exactly zero and **no negative** frame time values
- time-value range 0 to 10,000 (this range was observed privately;
  the public analyzer returns buckets only)
- no per-sequence signed 32-bit accumulation overflow
- **two sequences** with differing frame time values between source
  resolution packs
- all 2,351 nonempty sequences have a positive cumulative time
- 3 empty sequences have zero cumulative time
- serialized frame read-bool bytes observed only as 0 and 1

This is **data-format** evidence, not a measured frame rate or
on-device gameplay playback test. It doesn't demonstrate which
runtime update consumes or advances the saved counter.

## Code, testing, privacy

- `src/heman_tools/sprite_sequence_native_timing_ledger.py`
- `tests/test_sprite_sequence_native_timing_ledger.py`

The public regression suite uses **26 completely fabricated tests**:
boundary buckets, signed integer/zero handling, paired resolution
differences, oversized cumulative durations, empty sequences,
unusual boolean bytes, malformed repos/ZIP members, and safe output.

Run the source census only in a private owner-controlled environment:

```sh
PYTHONPATH=src python -m heman_tools.sprite_sequence_native_timing_ledger \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_sequence_native_timing_ledger.json
```

The `local_reports/` path is ignored. Do not publish original IPA,
executable, WADs, per-record timing, source asset names, textures or
runtime traces in public GitHub/Actions.

## Next proof obligation

Before driving Nintendo Switch sprite playback from native frame time
fields, confirm the **runtime tick unit, zero-time frame policy,
frame-boundary comparison, end-of-sequence loop behavior and signed
counter overflow strategy** in independently inspected original
update functions or private execution traces.

The synthetic NRO, original art integration and actor collision
bindings remain unchanged and unverified.
