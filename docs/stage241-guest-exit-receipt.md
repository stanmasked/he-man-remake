# Stage241 — distinguish emulator process exit from guest NRO exit

## Confirmed integration gap

The Stage240 private launcher records the exit code of the *emulator host
process*. That code is not necessarily the guest NRO program's exit code:
an emulator may close normally even if the guest was never loaded, crashed
or silently stopped before returning from \`main\`.

Stage241 extends the original-free Stage234 deko3d GPU probe. An outer
\`main\` calls the existing guest code and commits a new private SD file
after the guest function returns:

    sdmc:/switch/heman-stage230/guest_exit.txt

Exact one-line content:

    STAGE241_GUEST_EXIT nonce=<32-lowercase-hex> code=<decimal-guest-return>

The file is created by writing \`guest_exit.tmp\` first, flushing and
closing, then renaming to the final path. Failure to commit a guest exit
after a valid nonce results in process return code 30. The guest removes
the previous final/temp files at the start of each attempt; Stage231
PREPARE also removes them before launching a new session.

A malformed or absent session nonce means an early guest failure with
no valid nonce-bound exit receipt; such an attempt cannot satisfy the
Stage241 completion gate. Other post-nonce guest failures may leave
a nonzero \`guest_exit.txt\` for diagnosis.

## Private launcher binding

\`tools/stage241_guest_exit_receipt.py\` validates the exact grammar,
nonce and reported code. \`tools/stage240_private_emulator_launcher.py\`
now records the parsed guest receipt separately from the **host** process
code. A zero host status and perfect 512-byte upload/render captures
are not accepted by the launcher if the guest receipt is missing,
stale, malformed or reports a nonzero guest code.

The two fields must not be confused:
- \`host_process_exit_code\`: OS result of the emulator executable.
- \`stage241_guest_exit_receipt.guest_exit_code\`: CPU file content the
  guest *claims* to have written before exiting.

Even an exact nonce-bound guest-written status is forgeable and cannot
independently establish GPU execution, backend health, or authentic
Switch hardware execution. All reports retain
\`runtime_gpu_execution_attested=false\` and
\`guest_process_exit_independently_verified=false\`.

## Tests and CI

Synthetic unit tests cover exact/missing/nonzero/stale/malformed/oversized
guest status and a *fake runner* that produces both perfect GPU capture
files and an emulator host status of zero while omitting the guest exit.
The latter must not pass the Stage241 launcher completion gate.

The separate devkitPro CI cross-build checks that the newly compiled NRO
contains the Stage241 receipt markers and that both real DKSH files
remain structurally valid and embedded in RomFS. It still does not
execute GPU instructions.

## Privacy and evidence

Public repository: source, invented RGBA fixtures, unit tests, NRO/DKSH
build output without commercial assets.

Owner-private Google Drive: original iOS IPA and extracts, plus any actual
emulator/device SD capture, guest status, runner logs, hashes and reports.
Never post keys, firmware, original media or raw private captures in CI.
Downloaded archived builds must be independently verified via ZIP CRC,
file sizes and SHA-256.

No genuine GPU runtime capture or original iOS pixel parity was produced
during Stage241 code development.
