# Stage201 — bounded native Symbol frame assembly

Stage201 connects the Stage198 draw-command contract, Stage199 quad geometry and Stage200 UV corner mapping into one bounded CPU-side frame packet builder. It is still an asset-resolved reference layer, not a production renderer.

## Packet contents and ordering

For every unmasked source Symbol, the assembler emits one packet containing:

- original source-order index and cut handle;
- eight XY floats from the verified four-vertex fan geometry;
- eight UV floats in the native SpriteCut order `(u0,v0), (u0,v1), (u1,v1), (u1,v0)`;
- RGBA vertex color;
- native blend-override state and factors;
- the winding flag computed after Symbol-local transforms and before SpritePlayer-wide transforms.

Masked Symbols are omitted according to `(symbol_mask & active_mask) != 0`. Source indices are never renumbered, and the parallel cut-extent array still has one entry for every original Symbol, including masked entries.

## Safety and transaction semantics

- The entire draw-command list is validated before geometry assembly begins.
- A defensive maximum of 1,024 source commands bounds memory use. This is an implementation safety cap, not a claim about the original game's maximum frame size.
- Output capacity is checked before allocating or writing packets.
- The C99 implementation stages packets in temporary heap memory and copies them to caller output only after every drawable command succeeds. The output count and packet buffer remain unchanged on all reported failures.
- Missing arrays, malformed order, non-finite transforms, insufficient output capacity, and geometry failures fail closed.
- Signed dimensions/scales and out-of-range UV endpoints remain unnormalized; this layer does not crop, clip, synthesize pixels or look up original assets.

## Implementation and tests

Added:

- `native/include/heman_symbol_frame_assembler.h`
- `native/src/heman_symbol_frame_assembler.c`
- `native/tests/test_symbol_frame_assembler.c`
- `src/heman_tools/symbol_frame_assembler.py`
- `tests/test_symbol_frame_assembler.py`

The Python reference rejects a stale plan whose precomputed mask state disagrees with the requested active mask. Both implementations preserve source order and combine geometry, UV, color and blend metadata without making GPU calls.

Synthetic tests cover ordered multi-Symbol assembly, mask omission without renumbering, exact XY/UV ordering, color/blend propagation, invalid later commands, capacity failure, invalid transforms, command bounds and empty frames.

## Evidence boundary and next step

Stage201 proves only CPU packet assembly from already-resolved command metadata and cut extents. It does not extract or bind textures, run OpenGL, implement filtering/blending/masking on a GPU, composite a complete original frame, or demonstrate original-runtime pixel parity. The next step is a private one-frame integration harness that supplies verified cut dimensions and the existing UV metadata to this assembler, writes a bounded diagnostic packet dump, and compares it against an authentic original render before any Switch renderer wiring.
