# Stage227 — deko3d DKSH shader compilation and RomFS readiness

## Scope

Stage226's synthetic deko3d NRO cross-built a genuine GPU image-transfer
code path, but did not include actual vertex or fragment shader programs.
Stage227 adds a reproducible, source-only shader toolchain and packaging
gate, preparing for GPU texture sampling without confusing a successful
cross-build with a completed GPU draw.

This stage uses only synthetic shader code and Stage224's original-free
9×5 RGB fixture padded to a 16×8 RGBA8 image. Original commercial images,
the iOS IPA and source-resource identifiers remain excluded.

## Added

- `padded_texture_vsh.glsl`: a Vulkan-style GLSL 460 vertex pass-through
  for 2D quad coordinates and texture UVs.
- `padded_texture_fsh.glsl`: a fragment shader that actually *contains*
  deko3d/GLSL `texture(...)` sampler2D instructions with an explicit
  binding 0, ready to be connected to the Stage226 RGBA8 texture.
- The deko3d make target invokes devkitPro's `uam` compiler for both shader
  stages, places `padded_texture_vsh.dksh` and
  `padded_texture_fsh.dksh` in the NRO's RomFS, then runs `elf2nro`
  with `--romfsdir`.
- The guest refuses to proceed if RomFS initialization or either DKSH
  resource fails a bounded header/control/code/program-table check.
- `verify_stage227_dksh_bundle.py` independently checks the actual
  compiled shader files for DKSH magic, control/code bounds and program
  metadata. Public Python tests cover valid invented shader records and
  malformed magic, sizes, offsets and duplicate shader files.
- The dedicated deko3d Actions workflow verifies both DKSH outputs and
  archives shader binaries alongside the NRO, without original assets.

## Evidence interpretation

A successful Stage227 workflow would confirm that the genuine uam GLSL
compiler produced two structurally valid DKSH binaries and that the NRO
with the embedded shader assets cross-compiled and linked. The source
app's startup checks will validate embedded shader availability **only
if the app is actually launched**.

It does **not** yet:
- bind these programs to a deko3d drawing command;
- submit vertex data to a render target or present a GPU-rendered frame;
- read sampled GPU pixels back, on hardware or in an emulator;
- establish pixel parity with the original iOS game, SpritePlayer or camera.

The next milestone is to bind the shader stages and the Stage226 texture,
draw an actual textured quad, capture GPU-rendered pixel evidence, and
compare every relevant sample with the asset-free C99 reference. Any
emulator that lacks deko3d GPU operation support must not be treated as
proof of hardware behavior.
