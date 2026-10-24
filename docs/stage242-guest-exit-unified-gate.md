# Stage242 — unified nonce-bound guest exit acceptance

## Confirmed mismatch

Stage241 had already checked the NRO guest exit receipt in the Stage240
emulator launcher, but Stage236 --require-complete independently accepted
a pair of perfect captures without guest_exit.txt. The two entrypoints
therefore disagreed about the meaning of a completed synthetic capture.

Stage242 closes this gap: Stage236 now reads the guest SD receipt and uses
the Stage241 strict parser. A complete synthetic bundle requires:

- prepared NRO SHA-256 and SD challenge bound to the same Stage231 session;
- valid Stage234 final phase and nonce-bound Stage230 readback receipt;
- uploaded and rendered 512-byte RGBA buffers matching invented fixture;
- Stage231 collected report hash joins if a collected report is available;
- **valid Stage241 guest receipt**, same nonce, guest return code exactly 0.

Missing, malformed, stale nonce, nonzero or oversized guest receipts
make synthetic_bundle_consistent=false. Pixel diagnostics still survive.
Stage240's separate host exit and guest exit fields remain distinct.
Stage231's older COLLECT may label matching submitted RGBA as preliminary
evidence; Stage236/242 now rejects this as a completed bundle without a
guest receipt. No CPU receipt can independently prove GPU execution.

## Source-only CI matrix

The dedicated Stage242 workflow produces a five-scenario JSON report using
invented NRO0 and 16x8 RGBA bytes only:

1. Correct nonce and guest code 0: synthetically consistent.
2. Missing guest receipt: reject.
3. Guest code 25: reject.
4. Stale guest nonce: reject.
5. Malformed guest record: reject.

The report explicitly records GPU execution NOT verified, emulator
process NOT executed and original iOS graphics parity NOT verified.

## Evidence preservation

Public repository/CI contain only invented fixtures, Python tools,
derived JSON and source-free NRO/DKSH. Retain original IPA, extracted game
data, actual raw emulator SD captures and runtime logs on owner-private
Google Drive. Archive CI reports in the private Evidence Archive and verify
their SHA-256 upon re-download. Stage242 introduces no new guest NRO; the
last verified guest cross-build remains Stage241. Keep Draft until real
runtime provenance exists.
