# Stage229 — full synthetic GPU readback evidence (pending runtime)

## Evidence carried forward

Stage228 cross-built an AArch64 NRO with deko3d and embedded DKSH, but its
guest-side checker exposed only a mismatch count and eight mismatch examples.
That cannot independently establish all sampled pixels and does not prove
the GPU executed. Successful compilation is not runtime evidence.
The NeXium Stage225 software framebuffer is a CPU/libnx test, NOT deko3d GPU.

## Stage229 implementation

The guest now prints an ordered, complete readback after the GPU queue
reports idle, using exact markers:

- STAGE229_GPU_READBACK_BEGIN width=16 height=8 bytes=512
- STAGE229_GPU_READBACK_ROW y=N rgba=HEX (eight rows, 128 hex chars each)
- STAGE229_GPU_READBACK_END mismatches=N
- STAGE228_GPU_QUAD_READBACK pixels=128 mismatches=N

All 512 bytes originate from the independent offscreen GPU render target
after copyImageToBuffer, not the upload/staging buffer. CPU-only build jobs
do not emit those markers.

tools/verify_stage229_gpu_readback.py takes runtime stdout, an OS/runner
exit-status file, the exact executed NRO, and a runtime metadata JSON.
It reconstructs the 9x5 synthetic RGB fixture zero-padded to 16x8 opaque
RGBA8 and verifies every output byte. It rejects missing/duplicated/
reordered rows and markers, invalid pixel data, wrong dimensions, alpha
errors, nonzero reported mismatches, nonzero exits, missing NRO header,
mismatched NRO SHA-256, missing command or CPU-only runtime declarations.

A passing report indicates the SUBMITTED transcript matches the expected
pixels. It explicitly reports hardware_execution_independently_attested=false
because synthetic logs and runtime metadata can be forged. Only independent
runner/driver/device provenance can support a real GPU execution claim.
Synthetic fixture unit tests in GitHub Actions never count as GPU execution.

## Required evidence

A real Switch or GPU-capable emulator must run the exact Stage229 NRO.
Retain the complete unedited executable stdout, host-provided exit status,
independent GPU event/command diagnostics, the executed NRO, and a metadata
file with the following fields populated from that real run:

schema = stage229-gpu-run-v1
source_kind = real_runtime
runtime = switch_hardware OR gpu_capable_emulator
gpu_execution_observed = true
stdout_captured = true
runner_exit_code = 0
command = actual executable invocation
nro_sha256 = SHA-256 of the exact executed NRO

Local validation:

    python3 tools/verify_stage229_gpu_readback.py \
       runtime.log exit-status.txt heman_deko_png_transfer.nro \
       runtime-metadata.json --output stage229-validated-pixels.json

The verifier will not fabricate metadata or convert simulated fixtures into
real observations. Hardware/emulator execution has NOT been achieved in
this stage. Original iOS screen parity remains separately unverified.

## Privacy and retention

Public CI stores only synthetic NRO and tests. Preserve original IPA/assets,
raw emulator captures and logs in owner-only Google Drive; place derived
aggregate reports, SHA-256 manifest and short CI receipts in the separately
organized Evidence Archive. Verify download hashes independently and do not
delete Stage227/Stage228 archives.

## Status

- Complete source-only row export and host validation code: implemented.
- Native toolchain cross-build and Python/C99 CI: must pass independently.
- Real deko3d GPU execution and full output provenance: PENDING.
- iOS original graphics parity: NOT ASSESSED.
