# Stage234 — texture cache invalidation and last-known GPU phases

## Upstream deko3d audit

Compared source/maxwell/gpu_base.cpp of devkitPro/deko3d with the
Stage233 guest. The existing fragment draw invalidated
DkInvalidateFlags_Descriptors and DkInvalidateFlags_Shader. However
DkInvalidateFlags_Image, which maps to InvalidateTextureDataCache in
the SDK, was absent. Queue.waitIdle orders completion but should not be
treated as an explicit texture-data cache invalidation.

Stage234 adds a full deko3d GPU barrier and a combined invalidation of
Image, Descriptors and Shader caches before the fragment sampling draw.
This is a source-level correctness hardening, NOT evidence of a confirmed
GPU runtime defect. The SDK also validates descriptor-set alignment;
the existing generated descriptor and sampler allocations remain in
place, and the Stage233 independent upload/readback path is unchanged.

## Checkpoints

New guest file:

    sdmc:/switch/heman-stage230/gpu_phase.txt

It contains one line, exactly:

    STAGE234_GPU_PHASE nonce=<32 lowercase hex> phase=<phase_name>

where phase_name is one of:

1. 01_nonce_validated
2. 02_shaders_loaded
3. 03_texture_upload_queue_idle
4. 04_upload_pixels_match
5. 05_render_commands_submitted
6. 06_render_queue_idle
7. 07_receipt_committed

The guest removes the old phase file at start, writes each checkpoint
to a temporary file, flushes/closes and renames it as a last-known phase.
If writing a checkpoint fails, the guest returns exit code 29. The
render completion phase is written only after the Stage230 nonce-bound
receipt has been committed; early phases are not success receipts.

Because the existing Stage231 nonce request is required, a checkpoint
cannot be accepted as a new run if it refers to another session. A
process that terminates early may leave a checkpoint at 1–6 without a
final render receipt.

These checkpoints are emitted by **CPU control flow** after submitted
queue calls, not independently by the Tegra GPU. They are useful
diagnostics but must never be called proof of actual GPU execution.

## Private host inspection

After Stage231 PREPARE, a genuine Switch or GPU-capable emulator run,
and preservation of its SD contents:

    python3 tools/verify_stage234_gpu_phase.py \
      --phase /private/sd/switch/heman-stage230/gpu_phase.txt \
      --session /private/session/stage231_session.json \
      --receipt /private/sd/switch/heman-stage230/readback.receipt \
      --require-complete \
      --source switch_gpu_png/source/main.cpp \
      --output /private/session/stage234_phase_report.json

For partial/failed runs omit --require-complete and, if the final
checkpoint was never reached, omit --receipt to inspect the last-known
phase. The verifier requires the exact 32-character nonce and known
phase grammar, checks the final nonce-bound receipt, and explicitly
returns gpu_execution_independently_attested=false.

The source audit checks all seven phase markers once each, including the
ordering `queue.submitCommands` → `05_render_commands_submitted` →
`queue.waitIdle` → `06_render_queue_idle` → render-target readback, as well as
the explicit draw-time texture-cache invalidation before readback. Unit tests deliberately
use invented phase files and forged nonce records; passing these tests
is not GPU evidence.

## Evidence and data retention

- Public GitHub: invented 16×8 RGBA fixture, C++/Python source/tests,
  compiled deko3d probe NRO, 512-byte synthetic DKSH programs.
- Private Drive: original iOS IPA, extracted commercial textures,
  any actual device/emulator SD captures and guest logs.
- Private Evidence Archive: checked source-free build artifacts,
  derived reports, manifests, SHA-256 and CI receipts.
- Never upload original assets to public CI.
- On each successful archived cross-build, re-download from Google
  Drive and independently verify byte count/ZIP CRC/SHA-256.

Neither Stage234 source checks nor the six CPU checkpoints establish
GPU sampling correctness, nor the pixel parity of the original iOS game.
Genuine runtime capture remains an open acceptance gate.
