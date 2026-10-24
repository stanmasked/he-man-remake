# Stage226 — deko3d GPU image-transfer probe (separate NRO)

## Why this is a distinct target

Stages 223–225 reproduce the source-audited iOS PNG allocation/padding
in portable C99 and draw it through a **CPU software framebuffer**.
Those checks do not create a Switch GPU image, issue texture-transfer
commands or establish hardware texture sampling.

Stage226 introduces a deliberately separate optional NRO target using
**deko3d**, Nintendo Switch homebrew's low-level GPU API. This is an
early integration and build test, not a replacement for the existing
libnx software framebuffer or the original game renderer.

## Specific implemented GPU actions

A synthetic nine-by-five RGB image is generated in memory; Stage224's
actual native C99 uploader expands it into a 16-by-8 RGBA sampled
footprint. Its right/bottom texels are black with opaque alpha, while
all original synthetic image pixels and row strides are preserved.
No original commercial art or original code is bundled.

The C++ test then uses the real deko3d API to:

1. Create a deko3d device and graphics queue.
2. Define an RGBA8 image layout and allocate GPU image memory.
3. Allocate CPU-visible staging memory and copy the validated C99 texels.
4. Record `copyBufferToImage` into a deko3d command buffer.
5. Submit the command list to the graphics queue and wait for completion.
6. Initialize an image descriptor and nearest/clamp sampler descriptor.

The new `switch_gpu_png/heman_deko_png_transfer.nro` is compiled by a
dedicated devkitPro/AArch64 workflow, with an independent NRO0/architecture
check and asset privacy gate.

## Build

```sh
make -C switch_gpu_png clean all
```

The ordinary synthetic raster NRO and the Stage224 padded software
framebuffer NRO are untouched.

## Critical boundaries

- **A successful build only establishes API and linker compatibility.**
  It does not confirm that the GPU commands executed in an emulator
  or on physical Switch hardware.
- Even successful GPU command submission would not establish actual
  *texture sampling*, framebuffer readback or pixel-perfect rendering.
  There is no shader, onscreen deko3d quad, framebuffer capture or
  texture readback in Stage226.
- Stage225 NeXium framebuffer pixels are CPU output only and cannot
  substitute for Stage226 native GPU execution.
- Original iOS gameplay camera, SpritePlayer runtime timing, real
  gameplay captures and their pixel parity remain unresolved.

The deko3d API usage is adapted conceptually from official devkitPro /
switchbrew sample patterns, using independently authored code and only
synthetic data:
https://github.com/devkitPro/deko3d
https://github.com/switchbrew/switch-examples/tree/master/graphics/deko3d

Next steps: confirm cross-build, arrange a guest/hardware GPU execution
environment that supports deko3d, add a textured shader, perform a GPU
sample/framebuffer readback and compare that captured image against the
Stage224 native C99 reference.
