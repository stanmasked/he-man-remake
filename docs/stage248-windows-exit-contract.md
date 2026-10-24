# Stage248 — gated Windows launch exit-code contract

## Goal

The Stage247 trampoline now launches the target only after Job Object
assignment. Stage248 verifies that the wrapper preserves the emulator's exit
code and surfaces launch failures rather than turning them into a false
success.

## Synthetic Windows cases

1. A source-authored Python child prints a unique marker and exits with code 7.
   The wrapper must return 7, the marker must reach the bounded log, the output
   drain must finish, and the Job Object must report zero active processes.
2. A deliberately nonexistent executable simulates the target disappearing
   after initial path validation. The wrapper must report
   STAGE247_GATED_LAUNCH_FAIL and exit with code 127, with no remaining process.

The Windows-only CI report uses invented host processes and records that GPU
execution and original iOS parity are not verified.

## Acceptance

The host exit code remains distinguishable from the NRO's separate
nonce-bound guest exit receipt. Neither a wrapper exit code of zero nor
synthetic host output is accepted as GPU provenance. Stage231 collection and
Stage241/242 guest gates remain unchanged.
