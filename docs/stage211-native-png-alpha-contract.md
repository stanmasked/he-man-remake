# Stage211 — native PNG alpha-transform contract

## Source-level finding

The original PNG loader has a per-texture alpha-transform switch. When the switch is 1, PNGData registers its RGB-by-alpha row callback; when it is 0, the loader registers a no-op callback. The transform only runs for decoded rows that contain an alpha channel.

For each RGB channel the original callback computes:

```text
(channel * alpha + 127) >> 8
```

The alpha byte is preserved. The right shift is by eight bits, so the source behavior is intentionally modeled exactly instead of substituting a more conventional divide-by-255 premultiplication formula.

## Correct TextureData field mapping

The callback flag is scalar-block byte 5. It is distinct from the signed 32-bit filter mode at bytes 6–9. A first aggregate pass incorrectly counted the 292 mode-1 filter records as alpha-transform-enabled; Stage212 corrected that mapping against the original ARMv7 loader and the TextureData parser.

The corrected owner-local audit found that the alpha-transform flag is 0 in all 1,645 indexed TextureData records in each screen pack. The selected eight-Symbol diagnostic frame also has the flag disabled for all eight references and all five unique textures. Thus this helper accurately models the native optional code path, but the current IPA metadata does not enable that path for any indexed TextureData record.

## Implementation

The helper in src/heman_tools/native_png_alpha.py models only the decoded-row transform. It does not decode PNG files, expand palette/tRNS data, allocate power-of-two textures, fill texture padding, flip rows, or upload to a GPU. Those operations remain separate and must preserve the order established by the native loader.

TexturePixels consumes bytes in native-upload representation. A caller must apply this helper only when the actual alpha-transform flag is enabled and the decoded PNG has alpha; it must not premultiply every texture unconditionally.

## Validation and limits

Nine synthetic unit tests cover enabled/disabled flags, alpha-channel absence, zero and full alpha, exact rounding, input length, dimensions and the byte bound. The local IPA audit confirms paired TextureData indexes and WADs are identical. No resource names, per-resource mappings, original image bytes, private selectors or binary hashes are retained in the public repository.

This stage confirms the source-level preprocessing rule and the current flag census. It does not establish GPU texture-upload behavior, exact original screen projection, GLES parity, or physical Switch output.
