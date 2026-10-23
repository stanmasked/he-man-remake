# Stage189 — private single-symbol frame crop proof

Stage189 follows the alias audit with a private end-to-end decode of one original frame. A local prototype successfully resolved the short idle alias to the east-facing sequence, parsed its first frame, resolved the symbol's cut handle, followed SpriteCut → TextureData → ImageData, and cropped the source PNG. The resulting local crop is **61×91 pixels** from a **250×93** source PNG. No image or source asset is committed.

## What this proves

- A serialized directional alias can select an exact sequence key.
- The original sequence record can be parsed to exact EOF and a frame symbol identified.
- The Symbol cut handle selects a specific SpriteCut tuple.
- The cut record's texture key resolves through TextureData and ImageData.
- The rectangle lies fully inside the source PNG; the crop succeeds without clipping or resizing.

## What this does not prove

- The crop is one sprite symbol, not a complete multi-symbol animation composition.
- The six Symbol transform floats are checked for finiteness but are not interpreted or applied.
- The C++ gameplay-state handle → alias/message mapping remains unverified.
- This does not establish animation timing, draw order, mirroring, blending, or visual parity in NeXium or on Switch.

## Implementation and privacy

Added `src/heman_tools/private_single_symbol_frame_decoder.py`, a private local CLI that reads the owner-held IPA and writes its PNG only under ignored `local_reports/`. Its JSON report contains aggregate properties only: no alias label, resource key, archive path, offset, raw source bytes, or per-record data.

The new `tests/test_private_single_symbol_frame_decoder.py` uses fabricated records and generated PNGs only. It covers strict single-symbol parsing, alias ambiguity, cut-handle resolution, PNG bounds and fail-closed behavior. The private IPA and rendered crop are not used by public CI.

## Next step

Build the multi-symbol composition path only after resolving the six transform fields and their coordinate origin. In parallel, trace how the C++ state machine selects an alias and how the four-slot component selector relates to east/west resources. Then compare a full rendered frame against the original source in a private emulator run.
