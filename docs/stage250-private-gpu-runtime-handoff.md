# Stage250 — private GPU runtime handoff

## Current artifact

Stage249 produced a deko3d NRO containing the vertex and fragment DKSH programs:

- NRO size: 227,064 bytes
- NRO SHA-256: 334274c91b4a90c6a4ecc4c018f11188c254b0f848fe3312bcbcf6dc0e105016
- Private source-free build archive: owner-private Google Drive Evidence Archive
- NRO header: NRO0; both DKSH program markers are embedded in the NRO.
- Stage249 cross-build and source audit passed. This is not a runtime GPU result.

## Required local inputs

A genuine GPU-capable Switch emulator must be installed on the owner-controlled
machine. The launcher intentionally does not guess an executable or SD path.
Before a private run, resolve:

1. Absolute path to the installed emulator executable.
2. Exact directory that the emulator exposes as sdmc:/.
3. An empty, owner-private session output directory.
4. The emulator's documented command-line arguments, with exactly one
   standalone {nro} argument. Configure its data directory so that --sd-root
   below points at the same SD root the emulator maps.

Do not put any of these machine-specific paths, emulator logs, SD captures,
or original iOS assets in GitHub. Keep them in the private Evidence Archive.

## Stage240 invocation template

The Stage240 launcher prepares a fresh nonce-bound session, launches the
explicit executable without a shell, caps combined stdout/stderr at 4 MiB,
collects host exit/log evidence, and checks the guest exit and capture bundle.
Replace every placeholder locally; the example is deliberately not a
copy-and-run command:

    python tools/stage240_private_emulator_launcher.py \
      --emulator "/absolute/path/to/installed-gpu-capable-emulator" \
      --nro "/private/path/heman_deko_png_transfer.nro" \
      --sd-root "/absolute/path/to/the-emulator-sdmc-root" \
      --session-dir "/private/evidence/stage250-session" \
      --timeout 300 -- {nro}

The final launch argument is replaced by the exact NRO path. If the emulator
needs additional documented flags, place them after -- and keep the
standalone {nro} argument exactly once.

## Evidence to preserve

A real run should preserve, privately and without editing:

- The launcher manifest (stage240_launch.json), host log and exit status.
- The same-session stage231_session.json and collected report.
- SD captures upload.rgba, readback.rgba, readback.receipt, gpu_phase.txt,
  guest_exit.txt, and run_nonce.txt.
- The exact NRO and emulator executable SHA-256 values.
- A screen recording or emulator-native trace showing which emulator/backend
  was launched, plus the derived validation reports.

Then run the Stage233 dual-capture verifier and Stage236 bundle collector
against that exact NRO, SD root and session. Preserve partial output too if
the run stops early; a missing receipt is diagnostic information, not a pass.

## Seven phase meanings

1. 01_nonce_validated
2. 02_shaders_loaded
3. 03_texture_upload_queue_idle
4. 04_upload_pixels_match
5. 05_render_commands_submitted
6. 06_render_queue_idle
7. 07_receipt_committed

These phases are CPU-written checkpoints. Even phase 7 plus matching synthetic
pixels is not independently verified GPU provenance. A real runtime attempt
and unedited logs/captures are required before drawing conclusions about
shader sampling or original iOS parity.
