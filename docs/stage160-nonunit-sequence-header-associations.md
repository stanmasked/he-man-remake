# Stage160 — non-unit sprite prefix values and nested-record alternatives

This is a **source-only**, read-only diagnostic stacked on Stage159.
The original iOS v2.0.0 IPA and its image/audio/pixel resources stay
owner-private. No original bytes, names, offsets, per-record numeric
header values or exact unclassified suffix lengths enter GitHub or CI.
The Switch NRO is unchanged.

## Question motivated by the previous private census

Stage159 found that **649/677** no-fit sequences have the first u32 of
their validated five-word prefix unequal to 1. Of 221 one-candidate
sequences in that group with a known initial cut key, zero had the
64-byte residual seen in all 708 counterpart firstword=1 records;
40 had 162 bytes, 67 had 576 and 114 had other residual lengths.

These results *suggest* that the serialized payloads may be
heterogeneous. They do not identify what the first word means.

## New tests of competing explanations

The Stage160 analyzer keeps exact first-word values **only in volatile
memory** to build an aggregate, anonymized association report:

1. How many distinct non-1 first-word values occur, and are their
   populations concentrated in one or many groups?
2. Do the same first-word values occur with more than one independently
   serialized candidate-count group (count=1, 2, 3–4, 5–10, 11+)?
3. For count=1 records with an *independently indexed* initial cut name,
   do repeated instances of the same first-word value always have the
   same remaining byte length, or can their exact lengths disagree?
4. Do any first-word values contain both rejected and fitted candidates
   under the Stage158 **hypothetical**, exact-EOF 64/82 grammar?
5. Are coarse suffix-motif totals and aggregate associations identical
   in the paired original screen packs?

The new report publishes only **counts of populations, distinct-value
counts, presence of mixtures, and the existing coarse suffix motifs**.
It does not publish the raw first-word values or record-level metadata.
Singleton groups never count as evidence for constant suffix size:
the uniform-versus-variable comparison requires at least two known
single-name records with the same in-memory header value.

An observed association would **not** prove a serializer type,
frame-count interpretation, original child boundaries, duration,
playback timing, collider switching or Switch fidelity. If lengths
vary within the same first-word value, that specifically refutes the
idea that the word alone determines the full record layout.

## Implementation and safety

- `src/heman_tools/sprite_sequence_nonunit_header_associations.py`
  reuses Stage159's strict cross-pack index, lexical and interval
  checks before the extra correlation calculations.
- `tests/test_sprite_sequence_nonunit_header_associations.py`
  has **16 fabricated-only checks**, including mixed first-word
  outcomes, mismatched suffixes, altered cut indices, pack divergence,
  duplicate ZIP members, selected ZIP symlinks and report redaction.
- All original classifications remain under ignored `local_reports/`.

Owner-private invocation (only on an authorized local source copy):

```sh
PYTHONPATH=src python -m heman_tools.sprite_sequence_nonunit_header_associations \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_sequence_nonunit_header_associations.json
```

**No Stage160 original-data results are claimed in this PR.**
Synthetic CI success, when observed, confirms the analyzer and its
privacy-safe fabricated tests only. The original IPA must be run
privately to determine whether these correlations exist in game data.

## Decision gate

If a non-1 first-word value can co-occur with incompatible suffix
lengths or competing grammar outcomes, reject the hypothesis that the
word alone selects a complete fixed nested layout. Otherwise collect
independent falsification controls and seek actual serializer /
runtime evidence before mapping any byte interval to game frames.
Do not silently import conjectural animation data into the Switch NRO.
