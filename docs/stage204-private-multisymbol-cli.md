# Stage204 — private multi-Symbol frame audit CLI

## Goal

Connect the Stage203 multi-Symbol parser and CPU packet assembler to an owner-local command-line path. The CLI resolves every Symbol in a selected frame through SpriteCut, TextureData and ImageData, validates source PNG rectangles, and emits aggregate-only evidence.

## Local invocation

Run from the repository root with the owner's local IPA and locally established private selectors:

```sh
PYTHONPATH=src python -m heman_tools.private_multisymbol_frame_audit \
  --ipa /secure/local/path/He-Man-v2.0.0.ipa \
  --region START:END --region START:END \
  --alias PRIVATE_ALIAS --variant 0 --direction east --frame 0 \
  --active-mask 0 --report-out local_reports/multisymbol_frame_audit.json
```

The byte windows and alias are private source-data selectors and must be supplied locally. Do not publish them with original source identifiers. The CLI never uploads the IPA, source images, resource names, byte offsets, coordinates or hashes. Its report is restricted to counts and boolean verification gates under ignored `local_reports/`.

## Validation

- Requires exactly two non-overlapping source-data regions and a resolved east/west alias pair.
- Checks both original screen packs' GO data and SpriteSequence index equality, plus SpriteCut, TextureData and ImageData repository equality.
- Rejects duplicate ZIP members, unsafe or oversized PNG members, ambiguous case-folded paths, unresolved links, invalid rectangles and out-of-range frame indices.
- Resolves every Symbol in source order, then calls the bounded Stage203 CPU packet assembler once for the complete frame.
- The active mask is an explicit auditor input, not inferred runtime state. The SpritePlayer transform is identity because live player state is not reconstructed here.
- CI uses synthetic fixtures only; it never receives the owner's IPA or extracted resources.

## Original-IPA verification — 23 October 2026

The exact repository CLI was run locally against the owner-held `He-Man-v2.0.0.ipa` for the same selected eight-Symbol frame in both directions. Both invocations exited successfully.

| Aggregate check | East | West |
|---|---:|---:|
| Source / resolved Symbols | 8 / 8 | 8 / 8 |
| SpriteCut rectangles in bounds | yes | yes |
| Resource links resolved uniquely | yes | yes |
| Source PNGs validated | yes | yes |
| CPU packets assembled | 8 | 8 |
| Vertices / UV pairs / color channels | 32 / 32 / 32 | 32 / 32 / 32 |
| Finite CPU packet values | yes | yes |
| Source order preserved | yes | yes |
| Masked Symbols (auditor mask = 0) | 0 | 0 |

The first attempted selector was rejected because its selected sequence did not contain frame 7; the CLI correctly failed closed. The sequence and frame were then reselected from source metadata, and the exact CLI succeeded without changing parser strictness. The private selector values and JSON reports remain local.

## Evidence boundary

This proves source-level resolution and bounded CPU packet assembly for the selected frame in `screen-med`. It does not prove GPU submission, blend-state equivalence, scene placement, non-identity SpritePlayer transforms, active runtime mask state, animation timing, or original-runtime pixel parity. The original IPA, extracted images, private selectors and reports are not committed or uploaded as Actions artifacts.
