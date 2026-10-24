# Stage254 — safe SD capture preparation

## Purpose

Stage253 validates a fresh preflight before Stage240 begins. Stage254 hardens
Stage231 itself so direct or future callers cannot accidentally follow a
pre-existing symlink at the SD root, switch, or heman-stage230 directory
when preparing the capture session. The preparation routine also refuses a
symlink or non-directory at the session output path.

## Changes

- The SD root must be a real directory, not a symlink or file.
- switch and heman-stage230 are checked one component at a time with
  lstat; missing components are created individually and then rechecked.
- The directory chain is checked again before stale capture artifacts are
  removed and before the nonce file is written.
- Session output paths are inspected with lstat before listing or creating
  them; symlinks and non-directory entries are rejected.
- The checks raise SessionError and do not write the Stage231 manifest or
  nonce into an external symlink target.

This closes the ordinary preflight-to-PREPARE substitution path when a
symlink is already present at a checked boundary. It is not a kernel-level
directory lock and does not claim protection against a hostile process that
races every individual filesystem operation. The Stage253 gate remains
mandatory for real Stage240 launches.

## Validation

The Stage254 workflow uses temporary synthetic files only. It runs Stage231
session tests, Stage240 launcher regressions, and Stage252/253 gate tests,
including new tests for symlinked switch and heman-stage230 directories.
No real emulator, GPU, original iOS resources, IPA, firmware or keys are used.

All summaries continue to state:

- real_emulator_launch_performed=false
- runtime_gpu_execution_attested=false
- gpu_capability_independently_verified=false
- original_ios_graphics_parity_attested=false

## Next step

Keep the Stage254 PR in Draft until the new workflow and core regression
matrix pass. Before a real launch, generate a private owner-host Stage252
report for the actual emulator, NRO, mapped SD root, session path and exact
arguments, then pass that report to Stage240. Archive all real-host reports
and outputs privately, verify downloaded copies by SHA-256, and do not claim
GPU execution without independent runtime evidence.
