# Stage261 — Mach-O physics/collision symbol-table census

## Goal

Stage260 counted printable strings. Stage261 parses the original thin 32-bit Mach-O's LC_SYMTAB and LC_SEGMENT records and separates symbols defined in the actual __TEXT,__text section from undefined or other-section symbol entries. This is stronger static evidence than a string match because the candidate names are associated with symbol-table entries whose section index points to executable text.

## Owner-private aggregate result

The original executable contains 62,689 nlist32 symbol-table entries and a 2,936,980-byte symbol string table. Category counts across symbol entries / entries defined in __TEXT,__text are:

- Physics: 695 / 528
- Collision: 150 / 118
- Sensor: 125 / 97
- Platform: 239 / 165
- Tile-map: 151 / 126
- Shape2D: 43 / 35

These are substring-category counts over symbol names, not counts of unique classes or runtime calls. Exact symbol names and the executable hash remain owner-private. The source identity and aggregate string counts are preserved in the [Stage260 private Drive handoff](https://docs.google.com/document/d/18qv5q_a8P_fETmdW8lAzBKGoPk5lo0V6TU01iudKFbM/edit).

## Method and limits

The tool validates load-command boundaries, section bounds, a single __TEXT,__text section, symbol-table and string-table ranges, each nlist32 string index and each NUL-terminated symbol name. The private report contains only aggregate counts and a SHA-256 of the executable. No raw symbol names or original binary bytes are emitted.

A symbol defined in __text is evidence that code or a code-section symbol is present in the binary; it is not proof that the symbol is reachable, called during Level 1-1, or linked to any particular .shape or .ps2d resource. This stage does not establish alpha-mask collision usage, physical behavior, or iOS gameplay parity.

## Public tests

The Stage261 workflow builds a synthetic ARMv7 Mach-O with a fabricated __text section, fabricated nlist32 entries and a synthetic string table. It tests category counting, defined-versus-undefined classification, malformed symbol offsets, absent symbol tables, redaction, IPA member safety and private output paths. The original IPA is never used in public CI.

## Next gate

The next step is to use private disassembly/reference analysis to investigate whether the text-defined collision and shape-loading symbols connect to the observed resource loaders. Keep call-graph hypotheses separate from proven references and runtime behavior. Do not import alpha masks into Switch gameplay until the resource binding or gameplay semantics are independently established.
