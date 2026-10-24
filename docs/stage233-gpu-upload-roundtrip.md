# Stage233 — separate GPU texture upload from fragment readback

## SDK audit

Review of devkitPro/deko3d implementation in source/dk_image.cpp confirms that the DkCopyBuf rowLength is a **byte pitch**. The previous value of zero is supported: it defaults to the rectangle width multiplied by bytes per pixel. DkImageFlags_Usage2DEngine is only required for transfer paths that actually select the separate 2D engine, not ordinary TransferCopy. The C++ ColorWriteState constructor calls dkColorWriteStateDefaults, so the existing empty-state construction enables RGBA writing. None of these findings should be misrepresented as an observed runtime failure.

Stage233 makes the 16x8 RGBA8 pitch explicit as 64 bytes/row, 512 bytes/layer for upload and output readback.

## Second independent GPU operation

Before drawing the Stage228 textured quad:

1. Upload the entirely invented 9x5 padded-to-16x8 RGBA bytes from CPU staging memory into a GPU image (existing code).
2. After queue idle, submit a **separate copyImageToBuffer command** from the GPU texture to a fresh, CPU-visible 4096-byte memory block.
3. Compare all 128 pixels (512 RGBA bytes) with the source-only C99 padded fixture. Emit STAGE233_GPU_UPLOAD_ROUNDTRIP with pixel count and mismatch count; return 16 on mismatch.
4. Persist the **GPU-readback** bytes to sdmc:/switch/heman-stage230/upload.rgba atomically. Return 17 if this separate capture cannot be stored.
5. Only then execute fragment-shader sampling and save the existing readback.rgba plus nonce-bound Stage230 receipt.

The original upload/staging memory is never mistaken for the Stage233 GPU copy. Both raw capture files are removed at start of every launch alongside the old receipt.

The Stage231 nonce-bound completion receipt and anti-stale checks remain intact; no receipt is committed if the upload roundtrip fails. The upload and render buffers are separate, so diagnosing a mismatch can distinguish transfer problems from sampler/raster problems.

## Owner-private validation

First perform the Stage231 PREPARE / genuine GPU-capable runtime / COLLECT workflow to validate the nonce, NRO hash, runner log and 512-byte render readback. Then verify both captures:

    python3 tools/stage233_validate_gpu_dual_capture.py \
      --nro /path/to/heman_deko_png_transfer.nro \
      --sd-root /path/to/real/emulator/sd       --session-dir /private/stage231-same-session

This second verifier requires the already collected Stage231 report, nonce-matching render receipt, correct NRO hash, exact 512-byte upload.rgba from the SD mapping and independent pixel equality of upload + render. It preserves upload.rgba and a derived Stage233 report in the PRIVATE session folder.

This validator and its invented unit-test fixtures **do not prove GPU execution**. A forged NRO log or bytes can pass both. Only independently observed GPU hardware/emulator execution and an unedited device/runner trace establish provenance; the report explicitly marks runtime_gpu_execution_attested=false.

## Evidence storage and gate

Public GitHub: synthetic code, Python tests, DKSH and cross-compiled NRO only.
Owner-private Google Drive: original IPA and extracted commercial data; real GPU runtime traces and both raw captures. Save derived hashes, CI receipts, and source-free ZIP in private Evidence Archive; re-download and SHA-256 verify.

Stage233 host validation and cross-build are separate from actual GPU runtime sampling. No emulator or hardware GPU capture is asserted by this stage; original iOS graphics parity remains unverified.
