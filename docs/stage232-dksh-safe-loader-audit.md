# Stage232 — safe DKSH shader loader preflight

The Stage231 compiled artifact contains two 512-byte DKSH programs (256-byte control + 256-byte code per shader), with one 64-byte program header beginning at byte 24. Review of the **actual deko3d SDK** (source/dksh.h and source/dk_shader.cpp in devkitPro/deko3d) confirms that the existing in-place control+code loading form is supported: dkShaderInitialize reads a header at the codeMem CPU address when ShaderMaker.control is absent. Therefore this stage intentionally preserves that supported layout rather than pretending to fix a proven shader failure.

## What changed

- Verify exact DKSH header size (24), magic, section alignment (256), bounded sizes (up to 4096 bytes each), and **one** vertex/fragment program.
- Verify the complete 64-byte DkshProgramHeader lies inside the control section, and inspect its type (0 for vertex; 1 for fragment).
- Require exact file length equal to control+code; reject truncated/trailing payloads.
- Before loading the program, validate aligned codeMem offset and capacity excluding DK_SHADER_CODE_UNUSABLE_SIZE (1024 bytes) at the end of the GPU code block.
- Keep the Stage231 nonce-bound SD readback and Stage229 full stdout rows unchanged.
- New independent tool tools/verify_stage232_dksh_loader.py mirrors the structural checks and also requires both exact DKSH binaries in the NRO RomFS, building on the Stage227 embedding verifier.
- Synthetic unit tests reject bad magic, stages, alignments, header size, truncated/trailing data, overlaps, and code-memory tail overflow.
- CI runs both Stage227 embedded-shader check and Stage232 strict loader check against newly compiled binary artifacts.

## Evidence and restrictions

These guards prevent malformed files from reaching GPU shader initialization. They do **not** establish the runtime correctness of the image/sampler binding, UV alignment, tile-to-linear copy, color channel order, synchronization, or that a compatible emulator/Switch ever executed the GPU draw.

The in-place deko3d method is SDK-supported but its runtime use remains unverified on hardware. No original iOS assets are included, and no commercial file is uploaded to GitHub. Keep the original IPA/extracted data and actual GPU captures in owner-private Google Drive, derived reports/CI manifests in the private Evidence Archive and verify downloaded archives by SHA-256 before considering evidence durable.

## Gate

- Stage232 source and synthetic tests: implemented.
- DevkitPro SDK cross-build: pending independent CI.
- Original iOS graphics pixel parity: not tested.
- Genuine GPU readback from Switch/emulator: **still pending**, and no false runtime receipt will be authored.
