# Stage239 — hash-join the Stage231 collected evidence

## Gap

Stage236 already matched the prepared NRO/session, SD nonce, phase and
receipt, and compared both RGBA captures. Its optional
\`stage231_collected.json\` check did not yet validate every hash that Stage231
had recorded, nor the private copies of the runtime log and exit status.

Stage239 extends the Stage236 bundle report to inspect the Stage231 private
collection outputs:

- \`readback.rgba\` and \`readback.receipt\` copied into the session folder;
- \`runtime.log\` copied from the runner's supplied log;
- \`exit-status.txt\` copied from the runner's supplied exit status;
- \`stage231_collected.json\` hash fields.

When the collected report exists, it is considered consistent only if its
nonce, NRO hash, result label, render SHA-256, receipt SHA-256 and runner-log
SHA-256 match the associated private files, the SD/private copies of render
and receipt are byte-identical, exit status is zero, and provenance remains
explicitly unattested. If a report exists but any link fails, the synthetic
bundle consistency gate fails. If the report is absent, the tool still
produces diagnostics for the raw captures and marks the report missing.

## Tests and limits

New synthetic tests verify the hash joins and deliberately modify a runner
log after collection; the changed log must be rejected. Tests use fake NRO
bytes and invented pixels only.

A hash join proves that files match the supplied manifest, not that the
runner log is truthful or the claimed GPU backend really executed. The report
continues to set \`runtime_gpu_execution_attested=false\` and
\`original_ios_graphics_parity_attested=false\`. Genuine device/emulator
provenance is still required.
