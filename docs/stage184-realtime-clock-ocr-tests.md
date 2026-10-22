# Stage184 — fail-closed tests for real-time clock guest evidence

Stage184 adds synthetic unit tests for the Stage183 OCR verifier. It does not change the Switch NRO, original-game research, or the runtime workflow.

## Covered behavior

- A PASS marker must appear in at least one late guest frame (frame 120 or 300); an early frame alone cannot satisfy the runtime gate.
- A frame containing both PASS and FAIL is not accepted.
- Missing captures, unsupported framebuffer dimensions, non-PNG payloads, and nearly blank guest frames are rejected.
- Tesseract execution errors propagate as verification failures.
- Tests generate temporary synthetic PNGs and mock OCR output; no emulator captures, original assets, IPA bytes, or private reports are stored in the repository.

## Validation

The eight new tests were run locally against the Stage183 verifier with Python and Pillow. They passed. The repository's Python matrix and native C99 matrix must still pass on the new PR head before this test layer is considered integrated.

## Evidence boundary

These tests verify the verifier's decision rules, not whether NeXium actually passes Stage183. The real-time NRO cross-build and guest-runtime workflow remain separate evidence gates. Stage183 remains a Draft PR until its current-head jobs complete.
