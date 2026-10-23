# Stage203 — bounded multi-Symbol CPU frame packet audit

## Goal

Extend the Stage201 packet assembler and Stage202 private-data research from a single isolated Symbol to a complete source frame containing multiple Symbols. This stage stops at CPU packet assembly; it does not add GPU calls or claim original-runtime pixel parity.

## Implementation

- `parse_symbol_frame` strictly parses a selected frame and retains each Symbol's serialized fields in memory in the original order.
- `parse_single_symbol_frame` remains a compatibility wrapper and still rejects frames containing anything other than one Symbol.
- `_assemble_private_symbol_frame_packet_summary` builds one ordered render plan, validates parallel per-Symbol rectangles, texture dimensions and wrap metadata, and calls the bounded packet assembler once for the complete frame.
- The helper emits aggregate counts and booleans only. It does not return resource keys, byte offsets, coordinates, image bytes or IPA hashes.
- The active mask must agree with the plan's suppression state. Omitted packets do not renumber surviving source-order indices.
- The SpritePlayer transform is explicitly identity for this isolated audit because runtime player state is not recovered from the serialized sequence record.

## Synthetic regression coverage

- Parse multiple Symbols without reordering or truncating the selected frame.
- Assemble multiple CPU packets while skipping a masked Symbol and preserving the surviving order.
- Reject metadata arrays that do not parallel the source Symbol list.
- Reject unsupported tween fields in a later Symbol without returning a partial summary.
- Preserve the existing single-Symbol compatibility behavior and unsupported-field failure tests.

## Private local evidence boundary

An independent local source-level replay against the owner-held IPA found a frame with eight Symbols. All eight selected SpriteCut regions were in bounds, each produced finite quad geometry and UV data, and all masks were zero. A private CPU-only preview was generated from the source crops in Symbol order.

This preview is an independent source-level composition, not a screenshot captured from the original runtime. It does not verify GPU texture sampling, filtering, blending state, full scene placement, player transforms or pixel parity. The IPA and extracted images remain local and are not committed. The exact repository CLI was subsequently run successfully on the same selected eight-Symbol frame in both directions; see [Stage204](stage204-private-multisymbol-cli.md).
