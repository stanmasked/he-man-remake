# Stage205 — paired screen-resolution frame parity

## Goal

Resolve the same private multi-Symbol frame from both iOS screen packs and compare the source-level geometry while keeping all original identifiers, coordinates, paths, and image bytes in memory. The result is an aggregate-only report under ignored `local_reports/`.

## Local invocation

Run from the repository root with the owner's IPA and private selectors:

```sh
PYTHONPATH=src python -m heman_tools.private_multisymbol_resolution_parity \
  --ipa /secure/local/path/He-Man-v2.0.0.ipa \
  --region START:END --region START:END \
  --alias PRIVATE_ALIAS --variant 0 --direction east --frame 0 \
  --active-mask 0 --report-out local_reports/resolution_parity.json
```

The CLI internally resolves `screen-med` and `screen-xlarge` independently, then compares per-Symbol records and assembled CPU packets. It never serializes private details.

## Original-IPA result — 23 October 2026

The exact paired-resolution audit completed locally for the same eight-Symbol frame in both east and west directions. All 13 parity checks passed in each direction:

- Eight Symbols resolved and eight CPU packets assembled in each screen pack.
- Every resource link resolved uniquely, all referenced PNGs decoded, all SpriteCut rectangles stayed in bounds, and all CPU packet values were finite.
- Symbol identity and non-position visual fields match; serialized X/Y offsets, SpriteCut rectangles, referenced PNG dimensions, and CPU XY geometry scale exactly 2× in the xlarge pack.
- The resolved Symbol → SpriteCut → TextureData → ImageData identity chain, native texture wrap codes, and native texture filter selectors match; normalized UVs, source order, RGBA values, blend overrides, and winding flags match across packs.
- The audit uses an explicit active mask of zero and an identity SpritePlayer transform; live runtime state was not recovered.

A synthetic negative control with an unscaled second pack was also exercised locally and correctly failed the 2× scale checks. The corresponding committed regression is included in the Stage205 test suite.

## Evidence boundary

This verifies paired source-resource and CPU-reference consistency for one selected frame. It does not verify GPU submission, actual Switch texture sampling, scene placement, non-identity player transforms, live active-mask state, animation timing, or original-runtime pixel parity. Original IPA bytes, extracted PNGs, private selectors, per-Symbol geometry, and JSON reports remain local and are not committed or uploaded as Actions artifacts.
