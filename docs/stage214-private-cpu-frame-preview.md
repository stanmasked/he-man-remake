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

## Evidence boundary

The synthetic integration tests validate the decode-to-CPU-render path and ensure unsupported mipmap mode is rejected. A private run against the original IPA is a separate gate. A successful CPU preview proves only that the selected source records and PNG textures can be assembled and rendered by this deterministic reference.

It does **not** prove GPU submission, GLES interpolation precision, original iOS runtime pixel parity, full-scene placement, or a playable remake. Keep the IPA, extracted PNGs, preview images and detailed reports local; never upload them to GitHub Actions or commit them.
