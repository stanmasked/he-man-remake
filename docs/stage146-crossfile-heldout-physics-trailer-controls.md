# Stage146 — cross-file holdout controls for unknown iOS physics trailers

## Original private iOS v2.0.0 observations

A read-only inspection of the owner's private original IPA reused
Stage145's 13 nonempty unknown physics trailers and 21 nonempty main-record
labels. All comparisons remain private and expose only aggregate counts.

Stage145 found **three** possible exact-EOF segmentations of multiple
unknown groups using names already known from main physics records.
Stage146 asks whether these are circular self-matches or whether
name evidence comes from **other physics resource files**.

The 13 nonempty trailers were evaluated with four independently
declared maximum unknown-byte widths: 16, 32, 48 and 96 bytes
per hypothetical group. Two key comparisons are:

| Source vocabulary used | Max 32 bytes: fits | Max 48 bytes: fits | Max 96 bytes: fits |
|---|---:|---:|---:|
| All nonempty main-record labels | 0 / 13 | 3 / 13 | 3 / 13 |
| Exclude labels supplied exclusively by the current file | 0 / 13 | 3 / 13 | 3 / 13 |
| Labels within the current file only | 0 / 13 | 0 / 13 | 0 / 13 |
| Labels observed in at least two different source files | 0 / 13 | 3 / 13 | 3 / 13 |
| Labels present only in other files, not the current file | 0 / 13 | 3 / 13 | 3 / 13 |

All **three surviving candidates** are multi-group cases. The
cross-file exclusion does not invalidate them, and the relevant
main labels occur in more than one distinct file. They disappear
under a maximum 32-byte unknown suffix, but reappear by 48 bytes.
These are limits imposed by the *test hypothesis*, **not decoded
original per-record data lengths**.

All ten other nonempty source trailers continue to reject the tested
label-plus-variable-suffix framing. None of the five vocabulary
controls or width tiers establishes the actual original record
layout, hitbox ownership, fixed numeric fields, game physics, or any
connection to Nintendo Switch runtime behavior.

## Implementation and privacy boundary

New module `src/heman_tools/physics_tail_crossfile_controls.py`
independently parses the main record labels of all paired original
physics files, holds out a target file's unique labels, compares
sources with repeated labels, and repeats the exact-EOF dynamic
programming check under predeclared widths 16, 32, 48 and 96.

It deliberately counts repeated labels **once per source file**,
not per record. It returns only fixed-mode aggregate 0/1/2+ counters
and explicit `false` runtime/geometry verification flags.

Owner-private command (no asset extraction):

```sh
PYTHONPATH=src python -m heman_tools.physics_tail_crossfile_controls \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/physics_tail_crossfile_controls.json
```

The original archive and all decoded strings/bytes/positions remain
outside public GitHub. `local_reports/` is gitignored. The public
regression suite is **17 fictional tests only**, with fabricated
physics records, UTF-16 labels, trailer bytes, paired ZIP archives,
size/security rejection and report redaction.

## Interpretation and next research gate

The three candidates are more robust than a self-referential label
match, yet this *cannot distinguish* a true field boundary from a
coincidental label appearing within the unknown payload.

Next investigate cross-file consistency of independently observable
data *other than labels*, e.g. typed length markers supported by
multiple files or known format-version structure, and seek evidence
from actual original iOS runtime frames when possible. Do not assume
that the 50-byte blocks or unknown suffixes encode geometry merely
because a lexical candidate fits.

Original Level1-1 collision import remains explicitly **blocked**.
