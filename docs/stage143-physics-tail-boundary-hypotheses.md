# Stage143 — falsifiable boundary models for still-unknown physics trailers

Stage142 established that 13 original iOS physics-structure files have
nonempty trailers with a total of 44 **declared** groups, but **did not
decode** individual group records. This stage introduces a bounded way to
test candidate boundaries without interpreting unknown source bytes.

## Candidate layouts under test

For each entire opaque trailer, use its already validated outer group
count and try two restricted, *hypothetical* repeated record patterns:

1. [u16 UTF-16 code-unit count + UTF-16LE label] [N opaque bytes]
2. [N opaque bytes] [u16 UTF-16 code-unit count + UTF-16LE label]

For a single tested file the same N must work for **every** group,
with N from 0 through 96 bytes. Only candidates that consume the
**entire** trailer exactly are recorded. UTF-16 must be structurally
valid and the declared number of groups must be honored. There is no
assumption that N really is padding, a position, a joint or a flag.

One-group trails are specifically marked **nondiscriminating**: any
valid first label followed by unknown bytes can trivially fit the
first model. Repeated zero bytes can create multiple equally plausible
frames. Both ambiguous and no-match cases are reported, not silently
recast as successful parsing.

## What can actually be concluded

Finding one or even a unique exact-consumption candidate on an
owner-private file is **still not proof** of a real original record
layout. The search space is intentionally small; a real format might
have variable-length sections, more nested data, per-group counts,
or fields that happen to look like UTF-16. A single ambiguous fit must
not be selected arbitrarily.

The aggregate-only local report includes file counts, declared groups,
how many files have no/one/multiple complete candidates and how
many multi-group files have any candidate. It excludes original
filenames, labels, inferred per-file widths, opaque bytes, offsets,
vertices and source hashes.

Run on the owner's private copy of the original iOS IPA only:

```sh
PYTHONPATH=src python -m heman_tools.physics_tail_candidates \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/physics_tail_candidates.json
```

The JSON stays in gitignored `local_reports/`. Public CI executes
only deliberately fictional fixtures.

The source-only Stage143 regression suite exercises exact EOF,
early truncation, trailing garbage, multiple labels, reversed field
order, UTF-16 corruption, one-group false confidence, ambiguous
all-zero records, variable-size bounds, archive security and
report redaction.

## Decisions held until independent evidence

- Trailer group field boundaries: **unverified**
- Trailer group types and semantics: **unverified**
- The preceding 50-byte physics parameter payload: **opaque**
- Mapping Level 1-1 objects to physical shape ownership: **unverified**
- Actual iOS physics and Switch remake parity: **unverified**
- Automatic collision geometry import: **not authorized**

Future work should first compare multiple independent layout
hypotheses against all 13 owner-private tails, then independently
corroborate candidate boundary structure through resource references
or original runtime behavior before assigning physics meaning.
