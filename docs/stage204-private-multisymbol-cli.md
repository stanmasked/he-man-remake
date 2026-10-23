# Stage204 — private multi-Symbol frame audit CLI

## Goal

Connect the Stage203 multi-Symbol parser and CPU packet assembler to a real owner-local command-line path. This stage resolves every Symbol in the selected frame through SpriteCut, TextureData and ImageData, validates all source PNG rectangles, and emits aggregate-only evidence.

## Local invocation

Run from the repository root with the owner's local IPA and the already identified private parameters:

```sh
PYTHONPATH=src python -m heman_tools.private_multisymbol_frame_audit \
  --ipa /secure/local/path/He-Man-v2.0.0.ipa \
  --region START:END --region START:END \
  --alias PRIVATE_ALIAS --variant 0 --direction east --frame 0 \
  --active-mask 0 --report-out local_reports/multisymbol_frame_audit.json
```

The byte windows and alias are private source-data selectors and must be supplied locally. The CLI never uploads the IPA, source images, resource names, byte offsets, coordinates or hashes. Its report is restricted to counts and boolean verification gates under local_reports/.

## Validation

- Requires exactly two non-overlapping source-data regions and a resolved east/west alias pair.
- Checks both original screen packs' GO data and SpriteSequence index equality, plus SpriteCut, TextureData and ImageData repository equality.
- Rejects duplicate ZIP members, unsafe or oversized PNG members, ambiguous case-folded paths, unresolved links, invalid rectangles and frames outside the 2–1,024 Symbol range.
- Resolves all Symbols in their original order, then calls the bounded Stage203 CPU packet assembler once for the complete frame.
- The active mask is an explicit auditor input, not inferred runtime state. The SpritePlayer transform is identity because live player state is not reconstructed here.
- Tests use synthetic PNGs and malformed inputs only. CI does not receive the owner's IPA or extracted resources.

## Evidence boundary

A successful CLI run would prove that the selected source frame can be resolved and converted to a bounded CPU packet sequence. It would not prove GPU submission, blend-state equivalence, scene placement, animation timing, or original-runtime pixel parity. Those remain separate gates.
