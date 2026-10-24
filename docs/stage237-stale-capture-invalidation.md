# Stage237 — invalidate stale capture files during PREPARE

## Gap and correction

Stage231 PREPARE previously removed the Stage230 render capture and receipt,
but did not remove the Stage233 upload readback or Stage234 phase checkpoint.
The guest clears these files when it starts; however, a run that never starts
could leave old files on the SD card. Stage236's nonce checks correctly reject
stale phase/receipt associations, but the PREPARE step should make freshness
explicit before the launcher is even invoked.

PREPARE now removes these eight files under only the synthetic test folder
\`switch/heman-stage230\`:

- \`readback.rgba\`, \`readback.receipt\`
- \`readback.rgba.tmp\`, \`readback.receipt.tmp\`
- \`upload.rgba\`, \`upload.rgba.tmp\`
- \`gpu_phase.txt\`, \`gpu_phase.tmp\`

It then writes the new \`run_nonce.txt\` and prepared session manifest as
before. No original game resources or paths outside this synthetic folder
are touched.

## Regression coverage

The Stage231 unit test creates all eight stale files, invokes PREPARE with a
fresh private session directory, and asserts every old artifact is removed
and the new nonce is present. These are filesystem/unit tests only; they do
not execute a Switch, emulator or GPU.

## Evidence handling

Raw captures and runtime logs stay in the owner-private Google Drive Evidence
Archive. Public CI contains only invented bytes and temporary fake files.
Keep the Stage234/235/236 acceptance gates unchanged: fresh files and matching
nonces do not prove GPU execution or original iOS graphics parity.
