# Stage230 — persist the deko3d offscreen GPU readback on SD

## Why this stage matters

Stage229 compiled guest code that prints all 512 bytes of an offscreen RGBA8
GPU readback to stdout. Not all Switch homebrew launchers/emulators expose
guest stdout. Therefore successful GPU commands might still produce no usable
log. Stage230 writes the exact 512-byte readback to the emulated/physical
SD card after queue.waitIdle and before the program returns.

## Files written on actual guest execution

Directory: sdmc:/switch/heman-stage230/

- readback.rgba — exactly 512 bytes; 16 columns × 8 rows × RGBA8.
- readback.receipt — one line:
  STAGE230_GPU_READBACK width=16 height=8 bytes=512 pixels=128 mismatches=0

The sample is **synthetic** (invented 9×5 source, zero-padded to 16×8).
No original iOS artwork, offsets or commercial assets are bundled.

The receipt is intentionally removed before writes begin and is committed
only after the binary payload was flushed, closed and renamed. A failed
write or SD mount/directory error produces guest code 26, never a successful
result without capture. A genuine pixel mismatch is also saved for diagnosis
and produces guest code 25 if saving succeeded. The file is a *runtime
output candidate* and can be edited/copied after the run; it is NOT
cryptographic proof of a Switch GPU operation.

If the launcher cannot expose stdio, the SD files remain available. This
also applies to emulators that expose a persistent sdmc drive mapping.
Do not use a CPU-only NeXium software-framebuffer capture as deko3d GPU proof.

## Independent host verification

The asset-free tool tools/verify_stage230_sd_gpu_capture.py checks:
- exact 512 bytes and receipt grammar, dimensions, zero mismatches;
- complete expected RGBA values, including right/bottom opaque-black padding;
- executed NRO0 header and SHA-256 against a separately supplied runtime
  manifest (the manifest MUST come from a genuine captured run);
- separately captured runner exit code of zero and declared GPU-capable runner;
- no unchecked file overflow; report marked
  hardware_execution_independently_attested=false.

Usage once actual runtime evidence exists:

    python3 tools/verify_stage230_sd_gpu_capture.py \
        readback.rgba readback.receipt heman_deko_png_transfer.nro \
        runtime-metadata.json exit-status.txt \
        --output stage230-validated.json

Metadata contract (values from actual runner, not unit tests):

    schema: stage230-sd-capture-v1
    source_kind: real_runtime
    runtime: switch_hardware OR gpu_capable_emulator
    gpu_execution_observed: true
    command: exact host invocation
    runner_exit_code: 0
    nro_sha256: actual binary SHA-256

Synthetic Python unit tests deliberately construct a fake NRO with NRO0
and plausible metadata. Passing tests **only** shows the validator rejects
bad inputs; the test is not hardware or emulator runtime evidence.

## Preservation and provenance boundary

Public GitHub Actions contains synthetic source code and an optional NRO,
but not original IPA files, extracted commercial textures or owner-private
runtime logs. Store readback.rgba, readback.receipt, actual emulator/console
diagnostics, separately recorded exit status and runtime metadata in an
owner-private Google Drive directory. Store derived hashes and CI reports
separately and re-download to check SHA-256. Keep Stage227–229 artifacts.

Stage230 acceptance:
1. AArch64 devkitPro build and C99/Python tests succeed.
2. Independent ZIP/NRO checks and owner-private archive backup succeed.
3. Real deko3d GPU readback remains **UNVERIFIED** until running the exact
   binary on actual Switch or demonstrably GPU-capable emulator with a
   device-side GPU completion record. A receipt alone cannot make that claim.
