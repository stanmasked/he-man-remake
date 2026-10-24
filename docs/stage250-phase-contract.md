# Stage250 — canonical Stage234 phase contract

## Problem

The bundle collector previously derived \`phase_index\` by sorting a set of
phase names alphabetically. The names happened to have numeric prefixes, but
alphabetical ordering placed \`05_render_commands_submitted\` after phases 06
and 07. A diagnostic report could therefore show the wrong progress index.
Stage235 also reported the raw phase without explaining what it does and does
not establish.

## Implementation

\`tools/stage234_phase_contract.py\` is now the single ordered registry used by
the Stage234 source validator, Stage235 capture analyzer, and Stage236 bundle
collector. It defines all seven phases in execution order and gives each a
conservative milestone, expected next step, and explicit evidence limitation.

The report distinguishes:
- \`05_render_commands_submitted\`: the guest reached the post-submit checkpoint;
  queue completion, CPU readback, and receipt commit are not established.
- \`06_render_queue_idle\`: the guest reports that \`queue.waitIdle()\` returned;
  CPU readback, pixel comparison, and final receipt are still pending.
- \`07_receipt_committed\`: the guest reports the final receipt checkpoint, but
  this is not independent GPU provenance or original iOS parity.

Unknown phase names are retained as diagnostic data but do not receive an
ordered index or a success interpretation.

## Validation

The Stage250 matrix feeds invented phase markers through the shared contract,
Stage235 analyzer, and Stage236 collector. All three must agree on the phase
index and next expected action. Regression tests specifically cover the
submitted/idle/receipt boundary and unknown phase handling. CI saves a small
JSON report containing only synthetic phase metadata.

## Evidence boundary

These are CPU-written markers and interpretations, not proof that the Switch
GPU or a genuine emulator executed the commands. Real GPU execution and
original iOS graphics parity remain unverified.
