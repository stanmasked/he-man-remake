# Stage215 — local transform provenance audit

## Purpose

Stage214 rendered one original multi-Symbol frame with an explicit identity `SpritePlayer` transform. Stage215 adds a privacy-safe summary of the per-Symbol transform fields already present in each selected frame record. This helps identify which local transforms affect the selected frame before comparing it with an authentic runtime capture.

## Source evidence boundary

The selected serialized Symbol record contains:
- integer prefix: cut handle, local rotation, local X/Y offsets;
- float block: alpha/red/green/blue multipliers and X/Y scales;
- scalar tail: four tween/easing selectors, blend-factor fields, and the Symbol mask.

The record does not serialize the current SpritePlayer-wide transform, its pivots/translation, runtime active mask, camera/view transform, or animation interpolation state. Stage214's identity player transform therefore remains an explicit isolated-preview assumption, not a recovered original runtime value.

## Aggregate-only report

The new `symbol_local_transform_summary` reports counts only:
- nonzero rotations and offsets;
- non-unit, negative, and zero scale axes;
- non-default color multipliers;
- nonzero masks and resolved blend overrides;
- histogram counts for each tween-selector group.

No resource names, exact offsets, raw scale/rotation values, source byte offsets, texture paths, or pixel data are included in the aggregate report. Malformed records fail closed. Synthetic tests verify both valid aggregation and rejection of incomplete records.

## Next evidence required

1. Use the aggregate to decide whether local per-Symbol transforms are material for the chosen frame.
2. Locate or recover the runtime SpritePlayer transform and active mask from independently verified source/runtime evidence; do not infer them from the GO frame alone.
3. Compare the same animation state against a trustworthy original iOS screenshot or capture. If no original runtime capture is available, record that limitation rather than claiming pixel parity.
4. Only after those values are grounded should the isolated CPU preview use a non-identity player transform.

## Status

Code and synthetic tests are prepared in Draft PR #207. GitHub Actions [run 39992081909](https://github.com/stanmasked/he-man-remake/actions/runs/39992081909) passed Python 3.10/3.12/3.13 and native GCC/Clang. A fresh private IPA run to generate this summary is still pending. Original IPA, extracted PNGs, screenshots, and detailed local reports remain private and must not be uploaded to GitHub Actions or committed.
