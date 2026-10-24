# Stage240 — private emulator process launcher

## Purpose

Provide an **actually executable host workflow** for Stage234's deko3d NRO,
rather than assuming a source cross-build or NeXium software framebuffer can
substitute for an observed Switch GPU run.

The local development container currently has no detected Ryujinx, Ryubing,
Yuzu, Citron, Sudachi or Vulkan inspection executable and no verified guest
GPU-capable runner. Stage240 does **not** install Nintendo firmware/keys,
bundle commercial data, invent GPU events or claim a real GPU run.

The host launcher can use a separately installed, legitimately configured
Switch emulator with an available GPU backend. Emulator-specific argument
handling changes by version: current Ryubing/Ryujinx variants may support
\`--no-gui\`/headless and \`--root-data-dir\`; consult the version's own help.
Crucially, \`--sd-root\` is the **actual mapped sdmc root**, not an arbitrary
temporary path. Otherwise NRO-written files will not be visible there.

## Owner-private invocation

Unpack the already verified Stage234 synthetic NRO from the private Evidence
Archive. On a host with an installed emulator, identify its real executable
and mapped sdmc directory. Make an empty, private session folder:

    python3 tools/stage240_private_emulator_launcher.py \
      --emulator /absolute/path/to/emulator \
      --nro /absolute/private/heman_deko_png_transfer.nro \
      --sd-root /absolute/path/to/real-emulator-sd-root \
      --session-dir /absolute/private/stage240-run-001 \
      --preflight-report /absolute/private/stage252-preflight.json \
      --timeout 300 \
      -- --no-gui --root-data-dir /absolute/private/emulator-data "{nro}"

The final argv is a **template**, not a universal Ryujinx command. The only
supported placeholder is a standalone literal \`{nro}\`, exactly once. Adapt
the flags to your installed emulator. A graphical emulator can use just
\`-- "{nro}"\` where direct file launching is supported, and must be closed
within the timeout.

The launcher uses \`shell=False\`, verifies executable and NRO paths,
computes SHA-256 of both binaries, and requires a fresh Stage252
preflight report for every non-test launch. Stage253 verifies the report
schema, all required checks, exact path and argument fingerprints, current
executable and NRO hashes, and a maximum 30-minute age before Stage231 PREPARE
can create a fresh 128-bit nonce. Only then does it start the **actual supplied
executable** with a bounded process timeout. The gate is a consistency check,
not a signed attestation: it cannot independently verify the operator's SD
mapping or GPU execution. It stores the process log and actual host exit status
privately. It attempts Stage231 COLLECT if the host exit is 0, and always
generates a Stage236 bundle report for partial or complete captures.

## Result files

Under the private session path:

- \`stage231_session.json\`: prepared challenge and NRO SHA-256.
- \`host-launch.log\`: host process stdout/stderr, never fabricated by tests
  when running the actual emulator.
- \`runner-exit-status.txt\`: actual host process exit, or 124 timeout/
  127 launch exception.
- \`stage240_launch.json\`: launcher executable SHA, argument vector, NRO
  SHA, process start/end, timeout status, submitted capture status and hashes.
- \`stage240_bundle.json\`: Stage236 private evidence consistency and
  Stage235 upload/render mismatch diagnostics, even for many partial runs.
- \`stage231_collected.json\`, \`runtime.log\`, \`readback.rgba\`, and
  \`readback.receipt\` when Stage231 COLLECT accepts a submitted capture.

The command returns 0 only when both Stage231 and Stage236 synthetic
consistency checks pass. This status is **not evidence of GPU execution**.
An emulator can terminate normally even if the *guest* NRO crashed;
host exit=0 must not be relabeled guest exit=0. The attempt manifest sets:

    emulator_gpu_capability_independently_verified=false
    guest_process_exit_independently_verified=false
    runtime_gpu_execution_attested=false

The report is still useful for triage: it shows exactly what executable was
run, when, how it exited and whether its SD files match the prepared NRO and
the synthetic pixel oracle. A fake local runner can also generate matching
bytes; tests demonstrate explicitly that such output remains unattested.

## CI, commercial files and safety

Public CI runs only simulated executables in a temporary folder with an
invented NRO header/bytes; \`--test-only-runner\` labels this use. Never
commit or upload real extracted iOS assets, Nintendo keys/firmware, or
raw device/emulator captures to public GitHub.

Private Google Drive Evidence Archive keeps actual launcher logs, SD captures,
session manifests and the commercial original IPA/extracted data separately.
Store derived reports, SHA-256 and source-only artifacts in their appropriate
archive subfolders and verify any copied ZIP by downloading it again.

No genuine GPU execution or original iOS pixel parity has been established
by Stage240's host test suite. GPU provenance remains a separate acceptance
gate requiring independently inspected GPU backend activity and real device
or emulator output.
