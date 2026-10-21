# Stage145 — original trailer name vocabularies constrain speculative record boundaries

The user-owned iOS v2.0.0 IPA was inspected read-only in a private
environment. No original game assets or source-specific decoded strings
were uploaded to GitHub or public CI. Stage144 had shown that arbitrary
variable-size unknown data can make 13/13 trailers fit hypothetical
UTF-16-label-plus-data records, but 11/13 admit multiple choices.

## Independent cross-resource vocabulary checks

Stage145 restricts the *same* strict exact-EOF, variable opaque-width
suffix hypothesis (0–96 bytes per group) with separately parsed
source vocabularies:

- Strings from the original main physics **record labels**, optionally
  retaining empty labels.
- Only the **nonempty** main-record labels.
- The main physics records' strings formerly found to resemble
  `.shape` names.
- The stems of independently structurally validated `.shape` files.

Each candidate must have a length-prefixed UTF-16 token from the
specified vocabulary for **every declared trailer item**. The remainder
is still unknown. A candidate is accepted only when it consumes the
entire tail without leftover bytes. Number of possible completions
is saturated to zero, one, or two-plus.

### Private aggregate results

The source has 81 physics structure resources, 409 standalone shapes,
21 distinct **nonempty** main-record labels and 13 nonempty trailers
(11 with multiple declared items).

| Token vocabulary required at every item | No fit | One fit | Multiple fits |
|---|---:|---:|---:|
| Known main-record labels including empty | 4 | 1 | 8 |
| Known **nonempty** main-record labels only | 10 | 3 | 0 |
| Known main-record shape-reference strings | 13 | 0 | 0 |
| Known global `.shape` filename stems | 13 | 0 | 0 |

For the strict **nonempty main-label** model all three one-fit cases
contain **multiple** declared trailer items. This is suggestive
lexical agreement, not proof of the actual repeated record format.
Conversely, the absence of any complete candidate under shape-name
and main shape-reference requirements **refutes those two direct-name
hypotheses under the tested framing**, not the existence of physical
shapes or indirect lookup relationships in the real game.

The source label results can arise by coincidence or incomplete
modeling, especially where the unknown portion is allowed to vary
between items. Do not assume a lexical label denotes a joint,
collider, trigger or playable object.

## Reproducible private-only gate

```sh
PYTHONPATH=src python -m heman_tools.physics_tail_lexicon_constraints \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/physics_tail_lexicon_constraints.json
```

The report is aggregate-only, under the already gitignored
`local_reports/`. It contains no original resource names, decoded
strings, per-item boundaries, byte offsets, candidate opaque widths,
geometry, original bytes or individual hashes. Both original
screen-resource packs are checked for byte-for-byte parity and all
source shapes are independently validated.

The public regression suite exercises invented UTF-16 labels, matching
and nonmatching shape vocabularies, empty labels, ambiguous all-zero
inputs, bad prefix/UTF-16 framing, bounded exact EOF, redaction,
malformed source envelopes, duplicate members, symlinks and
resolution-pack divergence. It never uses the original IPA in CI.

## Remaining blockers

- Original trailer record boundaries **unverified**.
- Meanings of the 50-byte parameter blocks **unverified**.
- Physics structure to Level1-1 object bindings **unverified**.
- Source game collision geometry and movement **unverified**.
- Real Nintendo Switch hardware and iOS gameplay parity **unverified**.

Next: test independent non-lexical constraints on the three remaining
multi-group candidate parses, or find format metadata that assigns
per-item lengths without a free padding parameter. Reject or quarantine
any hypothesis that only works by choosing one ambiguous path.
