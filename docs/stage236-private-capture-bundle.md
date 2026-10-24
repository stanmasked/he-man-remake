# Stage236 — private capture bundle and session join

## Purpose

Stage236 connects the existing Stage231 prepared session, Stage233 upload
capture, Stage230 render receipt, Stage234 phase checkpoint, current NRO hash,
and Stage235 mismatch diagnostics into one report. This helps keep a partial
or failed capture useful without mistaking missing files or mismatched
nonces for a successful run.

Tool: \`tools/collect_stage236_gpu_bundle.py\`

Example (all paths are private owner-controlled paths):

    python3 tools/collect_stage236_gpu_bundle.py \
      --nro /private/build/heman_deko_png_transfer.nro \
      --sd-root /private/sd-copy \
      --session-dir /private/session-2026-10-24 \
      --output /private/evidence/stage236_bundle_report.json

Add \`--require-complete\` to return exit status 2 unless the consistency
gate passes. The report is written first, so an incomplete session still
leaves useful diagnostics. A missing capture, phase or receipt is reported
as missing; wrong session IDs, stale receipts, malformed phase records,
incorrect capture sizes and pixel mismatches are visible rather than silently
converted to success.

## Cross-checks

- Recompute SHA-256 of the NRO and compare it with the prepared Stage231
  session manifest.
- Compare SD \`run_nonce.txt\`, Stage234 \`gpu_phase.txt\`, and the Stage230
  receipt nonce with the prepared session nonce.
- Parse receipt dimensions and preserve the guest's reported mismatch count.
- Include Stage235 per-pixel, per-row and candidate flip/channel diagnostics
  for any valid 512-byte capture.
- Mark the bundle consistent only when session links match, the final
  receipt-committed phase exists, the receipt reports zero mismatches, and
  both upload and render bytes match the synthetic fixture.

This gate is a **synthetic consistency check**, not a hardware execution
attestation. The report always sets \`runtime_gpu_execution_attested=false\`
and \`original_ios_graphics_parity_attested=false\`. Even a fully consistent
bundle may be fabricated or produced by a non-GPU process; independent
runner/device provenance is a separate acceptance requirement.

## Privacy

Run this tool locally against private SD copies and a private session folder.
Keep raw captures, original IPA, extracted commercial assets and runner logs
in the owner-private Google Drive Evidence Archive. Public CI uses only
invented RGBA data and fake NRO fixtures. Store only derived reports, hashes,
source-free build artifacts and CI receipts in the private archive.
