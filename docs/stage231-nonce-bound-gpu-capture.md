# Stage231 — nonce-bound deko3d capture handoff

## Purpose

Stage230 compiles an offscreen deko3d 16×8 readback that persists
512 RGBA8 bytes to sdmc:/switch/heman-stage230/readback.rgba and prints
a receipt. Stage231 binds each receipt to a fresh host-generated
128-bit random challenge, preventing an old receipt from silently
qualifying as the current run.

This is NOT cryptographic GPU attestation. A malicious party could
replay the entire NRO, challenge, output and log together. Genuine GPU
execution requires separate GPU-capable device/emulator diagnostics.

## Guest changes

Before romfsInit/device creation, the NRO:
1. Clears prior readback.rgba and readback.receipt including temporary files.
2. Requires exact 33-byte ASCII request file:
   sdmc:/switch/heman-stage230/run_nonce.txt
   Content = 32 lowercase hexadecimal characters plus final LF.
3. Rejects missing, malformed, uppercase or oversized requests (exit 28).
   Exit code 27 means SD preparation failed.
4. Executes the existing deko3d synthetic texture and GPU readback path.
5. Saves raw bytes and receipt with nonce= followed by 32 characters.
   Write failure returns nonzero and never commits a valid new receipt.

Stage229 full-rows stdout remains as independent diagnostic. No
commercial iOS game resources are embedded in the NRO.

## Owner-private host workflow

The portable tools/stage231_capture_session.py supports PREPARE and
COLLECT. PREPARE must point at the emulator's actual SD-card folder;
there is deliberately no guessed universal emulator path.

    python3 tools/stage231_capture_session.py prepare \
      --nro /path/heman_deko_png_transfer.nro \
      --sd-root /path/to/emulator/sdcard \
      --session-dir /private/heman-stage231-run-001

PREPARE checks NRO0 and SHA-256, generates a challenge via Python's
system CSPRNG, deletes stale readback outputs and writes run_nonce.txt.
No GPU command is executed by PREPARE.

Run the exact binary on a genuine GPU-capable emulator, preserving
unaltered runner logs, its actual launch command and independent
process exit. Emulator invocation is platform/configuration specific
and cannot be asserted without access to the actual runtime.
Record GPU command completion separately.

Once the real run finishes:

    python3 tools/stage231_capture_session.py collect \
      --nro /path/heman_deko_png_transfer.nro \
      --sd-root /path/to/emulator/sdcard \
      --session-dir /private/heman-stage231-run-001 \
      --runner-log /private/runner.log \
      --exit-status /private/runner-exit-status.txt \
      --runtime gpu_capable_emulator \
      --command "the actual emulator command with its arguments"

COLLECT rejects stale/wrong nonce, old or mismatched NRO SHA-256,
missing/short/extra readback, incorrect pixel content, malformed
receipt, missing log, nonzero/invalid exit, and repeated collection.
It preserves the submitted private raw data plus SHA-256 aggregate.
The report explicitly sets runtime_provenance_attested=false:
valid bytes/nonce/logs are not device-side GPU attestation.

For a physical Switch, place PREPARE's run_nonce.txt in the real
sdmc:/switch/heman-stage230 directory before launching the NRO using
hbmenu or netloader. Copy the two resulting files back into the
private SD mirror. A normal hbmenu launch may not provide independent
exit status, so only claim COLLECT passed with separate device/runner
evidence and a real exit receipt.

## CI and privacy

Synthetic Python tests intentionally fabricate fake NRO/captures to
exercise rejection logic. These must never be reported as GPU execution.
No emulator/hardware run occurred as part of Stage231 source authoring.

Public GitHub: invented fixtures, code, tests and cross-compiled NRO.
Owner-private Google Drive: original IPA, extracted resources,
actual runtime captures and runner logs. Evidence Archive: separately
retain derived reports, hash manifests and CI archives; verify after
download and preserve the Stage227–230 archives.

Stage231 runtime GPU evidence: PENDING.
Original iOS game pixel parity: NOT ASSESSED.
