# Stage 103 — private source-integrity gate for original Level 1-1

The experimental 3-room NRO has passed authentic NeXium execution
([Issue #97](https://github.com/stanmasked/he-man-remake/issues/97)).
The subsequent Level 1-1 lore rule core is tested under GCC and Clang
([Draft PR #109](https://github.com/stanmasked/he-man-remake/pull/109)).
**Neither achievement establishes the original iOS level geometry.**

## What the new gate does

`heman_tools.level11_private_readiness` reuses the existing private
`.lvl`→`.map` candidate identity/shape/collision cross-report audit and
combines it with:

- the original `MULevel1-1.lvl` / selected candidate `.map` screen-pair
  integrity report (exact version and file identity, declared byte parity),
- the existing eight-category manual-review checklist,
- an optional Stage 080 original iOS/Switch capture, timing and contact join.

The inputs must agree on the exact level/map candidate, have a unique
literal map reference, a unique named `collision` layer, internally
consistent screen-pair data, and complete valid boolean declarations.
Ambiguous links, incorrectly asserted source provenance, impossible
metadata and mismatched source-pack records are rejected or reported.

**The result is NOT a portable collision map and cannot turn metadata
into evidence of iOS gameplay.** Source integrity checks and even a
completed manual checklist do not authenticate camera calibration,
collision categories, object ownership, real input/video timing, or
proprietary game geometry. The output always contains:

`external_original_ios_frames_verified: false`

`original_map_collision_semantics_verified: false`

`switch_original_level_import_permitted: false`

`automatic_collision_export_permitted: false`

Source-derived map filenames, original asset paths, coordinates and
pixels never appear in the redacted output.

## Local-only usage

First create the three private original-source reports using the commands
in [first-level-cross-report-audit.md](first-level-cross-report-audit.md).
Generate the pair report from the *same* private iOS archive:

```sh
PYTHONPATH=src python -m heman_tools.first_level_pair_audit \
  --ipa "/your/private/He-Man-v2.0.0.ipa" \
  --level MULevel1-1.lvl --map MUMap1-1.map \
  --out local_reports/level11-pair.json
```

Keep a private `local_reports/manual-level11-review.json` containing
all eight keys of `heman_tools.level_evidence_gate.REQUIRED` and
explicit booleans. Missing or unverified declarations must be
`false`; arbitrary `true` values **do not authenticate footage**.
The command below runs without a source clip if none exists (and
explicitly records the missing evidence):

```sh
PYTHONPATH=src python -m heman_tools.level11_private_readiness \
  --links local_reports/level1-map-links.json \
  --shapes local_reports/level1-shapes.json \
  --collision local_reports/level1-collision.json \
  --pair local_reports/level11-pair.json \
  --manual local_reports/manual-level11-review.json \
  --out local_reports/level11-private-readiness.json
```

When a separately verified capture join exists, pass
`--captures local_reports/joined-evidence-summary.json`.
This still cannot turn self-declared clip metadata into authenticated
original iOS screenshots or authorize automatic collision export.

All source reports and the privately owned iOS IPA stay under the
ignored `local_reports/` folder or other private storage. The public
CI checks only **fabricated** input summaries, including malicious
contradictions and attempts to write outputs outside `local_reports/`.

The user's IPA is **not mounted in the current execution environment**.
No source data was read or converted during this stage. Exact map
membership, original geometry and source gameplay remain open in
[Issue #110](https://github.com/stanmasked/he-man-remake/issues/110).

## Tests

```sh
PYTHONPATH=src python -m unittest discover -s tests \
  -p test_level11_private_readiness.py -v
```

This is a research gate only. It has no effect on the existing Switch
NRO, experimental three-room gameplay or the lore module itself.
