# Stage199 — C99 native Symbol quad geometry

Stage199 advances the Stage198 command ABI into a geometry reference. The original iOS ARMv7 executable was inspected locally; no binary, IPA bytes, texture pixels, private keys, or per-record reports are committed.

## Original draw path confirmed

Read-only tracing of `SpritePlayer::updateMesh` and `SpritePlayer::paint` establishes:

- Each Symbol mesh slot advances by **0x38 (56) bytes**.
- The slot starts at the winding flag; the per-Symbol RGBA values begin at slot +4 bytes.
- Four XY vertices occupy slot +20 bytes (8 binary32 values).
- The UV pointer field begins at slot +52 bytes in the original 32-bit iOS object.
- `paint` passes the XY pointer to `glVertexPointer(2, GL_FLOAT, 0, ...)`, passes the separately built SpriteCut UV array to `glTexCoordPointer`, then calls `glDrawArrays(GL_TRIANGLE_FAN, 0, 4)`.
- The four vertex pairs are stored in source order as left/lower, left/upper, right/upper, right/lower. The winding flag is determined from the resulting signed area; the painter adjusts front-face state without sorting vertices.

This layout describes the original **32-bit iOS object**. The portable C99 result struct in this repository is deliberately not declared to be byte-for-byte ABI-compatible with that 32-bit pointer-bearing object on 64-bit host/Switch targets.

## Geometry and transforms

The helper constructs a centered quad from the signed SpriteCut width and height, then applies:

1. Symbol X/Y scale.
2. Symbol rotation using the native degrees-to-radians constant.
3. Symbol X/Y offset.
4. SpritePlayer rotation around its rotation pivot.
5. SpritePlayer independent X/Y scale around its scale pivot.
6. SpritePlayer translation.

This mirrors the two separately verified transform layers. The quad builder keeps the original four-vertex order. It does not sort vertices, clip dimensions, normalize UVs, or generate padding pixels. Zero/negative cut dimensions and zero/negative scales remain representable; non-finite results fail closed.

## Implementation

Added:

- `native/include/heman_symbol_mesh_geometry.h`
- `native/src/heman_symbol_mesh_geometry.c`
- `native/tests/test_symbol_mesh_geometry.c`
- `src/heman_tools/symbol_mesh_geometry.py`
- `tests/test_symbol_mesh_geometry.py`

The C99 helper accepts a Stage198 draw command, signed cut width/height, an optional player transform and an output structure. It validates the command and transform, computes the four XY points and winding flag, and writes output only on success. UV endpoints remain in the draw command. No GPU calls, original resources, or texture lookup are connected.

The Python reference mirrors binary32 intermediate rounding and transform order. Synthetic coverage checks native vertex order, local scale/rotation/offset, player pivots/order, mirrored winding, zero/negative dimensions, overflow rejection, UV immutability and input immutability. The native tests are wired into the strict GCC/Clang `native/run_tests.sh` matrix with floating-point contraction disabled for this executable.

## Evidence boundary / next step

The C99 quad geometry is now executable and testable, but it is not yet a renderer. The source UV corner ordering, texture binding, native blending/masking integration, actual frame assembly, and original-runtime pixel parity still need a separate end-to-end proof. The next step is to add a private, bounded multi-Symbol frame assembler that resolves each verified cut and passes its native dimensions/UVs into this geometry helper, then compare one complete frame against an authentic source render before any production Switch integration.
