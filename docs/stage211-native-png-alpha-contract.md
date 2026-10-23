# Stage211 — native PNG alpha-transform contract

## Finding

The original PNG loader has a per-texture alpha-transform switch. When enabled, PNGData registers its RGB-by-alpha row callback; when disabled, it registers a no-op callback. The transform only runs for decoded rows that contain an alpha channel.

For each RGB channel the original callback computes:

```text
(channel * alpha + 127) >> 8
```

The alpha byte is preserved. The right shift is by eight bits, so the source behavior is intentionally modeled exactly instead of substituting a more conventional divide-by-255 premultiplication formula.

The owner-local IPA audit confirmed that both screen-resolution resource packs agree and that the texture flag is boolean throughout the inspected records. No resource names, per-resource mappings, original image bytes, or binary hashes are retained in the public repository.

## Implementation

`src/heman_tools/native_png_alpha.py` models only this decoded-row transform. It does not decode PNG files, expand palette/tRNS data, allocate power-of-two textures, fill texture padding, flip rows, or upload to a GPU. Those operations remain separate and must preserve the order established by the native loader.

`TexturePixels` continues to accept bytes in native-upload representation. A caller must apply this helper only when the corresponding texture flag is enabled and the decoded PNG has alpha; it must not premultiply all textures unconditionally.

## Validation and limits

Nine synthetic unit tests cover enabled/disabled flags, alpha-channel absence, zero and full alpha, exact rounding, input length, dimensions and the byte bound. The local original-IPA check and an eight-Symbol CPU diagnostic preview remain in the private working environment.

This stage confirms the source-level preprocessing rule. It does not establish GPU texture-upload behavior, exact original screen projection, GLES parity, or physical Switch output.
