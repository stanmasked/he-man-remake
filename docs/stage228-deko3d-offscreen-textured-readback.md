# Stage228 — deko3d offscreen textured quad and readback (source/CI gate)

## Scope and ancestry

Stacked on Stage227 / PR #219. Uses the same invented 9×5 RGBA source
padded to 16×8, with nearest sampling; no IPA, original game artwork
or commercial resource identifiers are committed to the public repository.

The Stage227 shaders have real DKSH binaries embedded in NRO RomFS. This
stage goes beyond the compiled shaders by **recording** an actual deko3d
graphics command list with a textured quad draw and offscreen readback.

## Implemented code path

1. Verify both DKSH resources through the existing bounded RomFS preflight.
2. Copy both shader files into a GPU Code memblock at distinct aligned offsets;
   initialize the vertex and fragment shader objects, checking the stage.
3. Keep the Stage226 CPU-to-GPU texture upload and nearest/clamp sampler.
4. Allocate an independent RGBA8 render target with UsageRender; allocate
   descriptor sets, vertex buffer, GPU-to-CPU readback and command memory.
5. Bind the 2D vertices (position, UV), shaders, sampled image descriptor,
   sampler descriptor, raster/depth/color state, viewport and scissor.
6. Issue a triangle-strip draw for four vertices; apply the image barrier.
7. Transfer **the rendered target**, not the upload source, to an uncached
   CPU-visible readback buffer. Wait for the graphics queue to idle.
8. Compare 128 RGBA pixels to the synthetic C99-derived padded fixture.
   Return nonzero for mismatches and print at most the first eight mismatches.

The image sampler intentionally samples the entire padded 16×8 image so
alpha-opaque black padding is also exercised. This establishes a concrete
*runtime assertion* to be executed on a GPU, but a successful source build
does **not** establish that the assertion was executed.

## Evidence gates

- **CI cross-build success**: native AArch64 NRO compiles and the embedded DKSH
  bytes match the stand-alone shaders (source/package evidence only).
- **Actual execution**: requires a captured Switch/compatible emulator run
  showing `STAGE228_GPU_QUAD_READBACK pixels=128 mismatches=0`, correct exit
  status and an execution-specific artifact hash. This has not occurred yet.
- **Original game parity**: not evaluated. The fixture is synthetic and tiny.

Caution: color format/row pitch, UV orientation, scissor coverage or cache
ordering may differ at runtime. A mismatch is **not** permission to alter the
reference or silently skip rows. Capture diagnostic output, inspect and fix
the GPU path. The CI workflow must never claim a real sampled GPU frame.

## Preservation

The public repo contains only source and synthetic fixtures.
Keep original IPA, extracted assets, private emulator captures and raw logs in
owner-private Google Drive. Store derived reports, SHA-256 receipts and CI
metadata separately in the project's Evidence Archive; verify downloaded
artifacts against those receipts. Stage227's verified artifacts remain intact.
