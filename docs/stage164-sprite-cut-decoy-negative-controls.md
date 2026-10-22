# Stage164 — source-private negative controls for registered sprite-cut anchors

This stage builds on Stage163, which searches for exact length-prefixed
UTF-16 sprite-cut names without assuming a frame width. It is **not**
an animation decoder. The synthetic Nintendo Switch NRO is unchanged.

## Specificity question

Stage163 may find one or more independently registered cut names in
opaque record bodies. Those matches are lexical evidence, not verified
child frames. To detect whether *similarly shaped but unregistered*
tokens also occur inside the body, Stage164 introduces a matched-length
decoy registry as a negative control.

For every eligible printable ASCII cut key indexed independently in
`SpriteCutData.repo`, generate one **new, unique** name of the same
UTF-16 code-unit length. The decoy is chosen deterministically by
replacing one character; it must not collide with any genuine indexed
key or another decoy. Both the original names and the private decoy
names stay in memory only. If an eligible decoy cannot be constructed,
the analysis fails closed.

## Separate measurements

Using the exact same valid initial source-cut name as Stage163, scan
the remaining bytes in two independent passes:

- Registered cut-token pass — Stage163's established exact UTF-16
  name+length reference set
- Same-length decoy-token pass — identically framed but **not indexed**
  fabricated names, with the same registry cardinality

For each combination of firstword=1 / firstword other and the declared
candidate-count buckets 1 / 2 / 3–4 / 5–10 / 11+, collect only counts:

- Records with valid initial cut key
- Records with additional genuine indexed tokens in either/both source
  screen packs
- Records with additional decoy tokens in either/both packs
- Records containing both a genuine and a decoy in at least one pack
- Agreement counts for real registered anchor lists between packs

All real indexed-token categories are reconciled with the independent
Stage163 summary before exporting an aggregate report. No token strings,
raw field values, per-record results, byte positions or source pixel
information leave the private process.

This is a **limited specificity control**, not a calibrated statistical
randomization test. Deterministic substituted names might differ
lexically from true asset names, and zero decoy matches cannot prove
the genuine matches represent frames. Conversely, positive decoy
matches would demonstrate that exact length-prefix framing alone can
produce cut-like lexical occurrences unrelated to the cut index.

## Implementation

- `src/heman_tools/sprite_sequence_cut_decoy_controls.py`
- `tests/test_sprite_sequence_cut_decoy_controls.py`
- 20 fabricated-only regression tests: stable distinct decoys, collisions,
  deliberate decoy bytes, raw UTF-16 without length prefix, mixed real
  and decoy names, per-screen changes, firstword buckets, malformed
  cut indexes, ZIP duplication/symlinks and redaction

Private owner-only usage:

```sh
PYTHONPATH=src python -m heman_tools.sprite_sequence_cut_decoy_controls \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_sequence_cut_decoy_controls.json
```

`local_reports/` remains gitignored. No original IPA, sprite
WADs, names, bytes, per-record field values, offsets, exported images
or private reports may enter public GitHub or CI.

## Interpretation gate

Review private **registered-vs-decoy aggregate** evidence together with
Stages159–163 before identifying any tentative nested boundary.
Frame identity, count, duration, playback order, actors, hitboxes and
Switch game parity remain unverified even when real anchors outnumber
decoys. Runtime/serializer evidence is still required for animation
integration.

**No original IPA results are claimed for Stage164 in this session.**
