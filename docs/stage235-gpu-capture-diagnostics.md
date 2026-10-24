# Stage235 — synthetic GPU capture mismatch diagnostics

## Purpose

Stage235 adds a host-side diagnostic tool for the existing Stage233/234
private captures. It is useful when the guest reports a pixel mismatch or
stops before its final receipt: the analyzer can inspect each 512-byte
capture independently and compare it to the invented 16x8 RGBA fixture
without rejecting the evidence before a useful report is produced.

This is a diagnostic aid, not a new guest renderer and not GPU execution
evidence. The Stage234 NRO/DKSH bundle remains the tested build under review.

## Captures and analysis

Tool: \`tools/analyze_stage235_gpu_capture.py\`

Run against private copies of captures (never upload raw files to public CI):

    python3 tools/analyze_stage235_gpu_capture.py \
      --upload /private/session/upload.rgba \
      --render /private/session/readback.rgba \
      --phase /private/session/gpu_phase.txt \
      --output /private/session/stage235_diagnostics.json

The upload and render files are independently optional, but at least one
must be provided. Each present file must be exactly 512 bytes (16×8×RGBA).
The report includes SHA-256, per-byte and per-pixel mismatches, first
mismatch coordinates, mismatch counts per row, and upload-versus-render
differences when both exist.

The classifier compares against the known synthetic fixture under 4 spatial
orientations (identity, horizontal flip, vertical flip, both) and all 24 RGBA
channel permutations. It reports exact candidate transforms where found;
otherwise it reports the three closest candidates by pixel/byte mismatch.
Candidate matches are descriptions of byte relationships, not proof of a
driver bug or a diagnosis of the underlying cause.

Triage hints distinguish patterns such as:
- upload and render both match the fixture;
- upload matches, but render differs;
- upload and render are byte-identical but share a deviation;
- the two captures differ and need separate review.

The optional Stage234 phase string is parsed for diagnostics only and remains
explicitly untrusted. It is not cross-validated as a session attestation by
this analyzer; use \`tools/verify_stage234_gpu_phase.py\` for the existing
nonce/receipt gate.

## Privacy and acceptance gates

- Public repository and CI use only generated RGBA fixture bytes.
- Original iOS IPA, extracted commercial assets, raw Switch/emulator captures,
  runner logs, and per-run reports remain in the owner's private Google Drive
  Evidence Archive.
- Store only source-free NRO/DKSH build artifacts, derived reports, manifests,
  hashes, and CI receipts in the private Evidence Archive.
- Re-download every archived build artifact and verify byte count, ZIP CRC,
  and SHA-256.

The tool sets \`runtime_gpu_execution_attested=false\` and
\`original_ios_graphics_parity_attested=false\` in every report. It cannot
prove that the bytes originated from a real GPU, Switch, or emulator.
Authentic runtime provenance and parity with original iOS frames remain
separate, unresolved acceptance gates.
