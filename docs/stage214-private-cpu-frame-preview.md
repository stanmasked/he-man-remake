# Stage214 — private PNG-backed CPU frame preview

## Goal

Extend the Stage204 owner-local multi-Symbol resolver from packet metadata to an actual CPU-rendered preview. The preview reads original PNG textures directly from the owner-held IPA and applies the audited TextureData sampling state:

- byte 5: optional RGB-by-alpha transform flag;
- bytes 6–9: signed little-endian 32-bit filter selector (`0` nearest, `1` linear; `2` remains unsupported until mipmaps are implemented);
- bytes 10 and 11: independent S/T wrap selectors;
- byte 12: PNG/alternate payload selector, with the preview accepting only the confirmed PNG path.

The alpha transform is applied only when the byte-5 flag is enabled and the decoded PNG actually has alpha. It uses the established native integer expression; disabled flags leave decoded RGBA bytes unchanged.

## Local invocation

Run from the repository root. The byte windows and alias are private selectors discovered from the local IPA; do not copy them into public logs, GitHub comments, Actions artifacts, or committed documentation.

```sh
PYTHONPATH=src python -m heman_tools.private_cpu_frame_preview \
  --ipa /secure/local/path/He-Man-v2.0.0.ipa \
  --region START:END --region START:END \
  --alias PRIVATE_ALIAS --variant 0 --direction east --frame 0 \
  --active-mask 0 --screen screen-med \
  --preview-out local_reports/stage214-east-med.png \
  --report-out local_reports/stage214-east-med.json
```

Run separately for the paired resolution pack and the opposite direction. The PNG and JSON outputs are written only under ignored `local_reports/`; the JSON is aggregate-only and contains no original resource names, byte offsets, texture paths, source coordinates, pixels, or IPA checksum.

## Rendering contract

- Every selected Symbol is resolved through SpriteCut, TextureData, ImageData and its PNG member.
- The full PNG is decoded to RGBA; source rows are not flipped or padded by this tool.
- Each Symbol receives a private texture binding, preserving original source order and per-texture wrap/filter state.
- The Stage201 packet assembler produces geometry with an explicit identity SpritePlayer transform.
- The output projection translates the selected frame's native XY bounds into a transparent canvas, then trims only fully transparent padding without resampling any pixels. It does not infer a camera, viewport placement, scene transform, animation interpolation, or player-wide transform.
- Rendering uses the existing bounded Python reference sampler and blend model. Mipmap mode, alternate payloads, unknown wrap modes, invalid PNGs and out-of-bounds SpriteCut rectangles fail closed.

## Private local validation — 2026-10-23

The owner-held IPA was processed locally for the selected eight-Symbol frame in both directions and both resolution packs:

- All 8 Symbols resolved to 8 drawable CPU packets with pixel coverage.
- The paired-resolution geometry/UV parity audit passed independently for east and west.
- The selected frame uses five unique textures: four nearest-filtered and one linear-filtered; no selected texture requests mipmaps, and the alpha transform is disabled for all five.
- Native-bound render canvases were 756×756 for `screen-med` and 1512×1512 for `screen-xlarge`. Trimming only fully transparent padding produced preview images of 199×182 and 398×363 respectively; the rendered RGBA pixels were not resampled.
- The full TextureData census matched across both packs: 1,645 records each, 1,353 nearest and 292 linear, zero mipmap selectors, alpha transform disabled for all records, PNG payload path for all records, and no unrecognized S/T wrap selectors.
- Local Python suite: 2,122 tests passed. Targeted Stage201 assembler and Stage208 textured-quad C99 tests passed under both GCC and Clang. GitHub Actions run 39988119030 also passed Python 3.10/3.12/3.13 and native GCC/Clang before temporary source-handoff cleanup; the post-cleanup run remains the final CI gate.

No original IPA, extracted texture, preview PNG, private selector or detailed local report was committed or uploaded to GitHub.

## Evidence boundary

The synthetic integration tests validate the decode-to-CPU-render path and ensure unsupported mipmap mode is rejected. A private run against the original IPA is a separate gate. A successful CPU preview proves only that the selected source records and PNG textures can be assembled and rendered by this deterministic reference.

It does **not** prove GPU submission, GLES interpolation precision, original iOS runtime pixel parity, full-scene placement, or a playable remake. Keep the IPA, extracted PNGs, preview images and detailed reports local; never upload them to GitHub Actions or commit them.
