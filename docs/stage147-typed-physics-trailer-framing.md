# Stage147 — an exact typed envelope for all 44 original physics trailer items

## Original source evidence (owner-private read-only experiment)

In the user's original iOS v2.0.0 IPA the 81 paired physics
\`.ps2d\` / \`.pstruct2d\` resources include 13 files with nonempty
sections following the already-parsed main physics records. Previous
Stages143–146 showed that arbitrary variable-width UTF-16 token +
padding guesses are ambiguous and do not establish boundaries.

A separate private read of the **actual unknown trailer bytes**
identified an unexpectedly compact exact framing:

    u16_le text_length_utf16_code_units
    text_length * 2 bytes of UTF16-LE text
    u32_le variant_discriminator
    if variant_discriminator == 0:
        opaque_payload[33]   # total 37 bytes after the string
    elif variant_discriminator == 1:
        opaque_payload[25]   # total 29 bytes after the string
    elif variant_discriminator == 2:
        opaque_payload[34]   # total 38 bytes after the string
    else:
        fail closed

The owner-private structural audit parsed the **declared number of
items** in each of the 13 trailers and reached **exact EOF without
any leftover bytes**. The same source file bytes match their
corresponding resolution-pack peers.

| Evidence from actual original iOS archive | Count |
|---|---:|
| Total paired physics files | 81 |
| Trailers with declared items | 13 |
| Physics files with zero trailer items | 68 |
| Fully consumed typed trailer items | **44 of 44** |
| Variant discriminator 0 | 22 |
| Variant discriminator 1 | 13 |
| Variant discriminator 2 | 9 |
| Files with item-count or end-of-tail mismatch | **0** |

The result strongly supports these **structural boundaries** for this
original v2.0.0 asset set. It does NOT prove the variant discriminator
is an actual engine joint type, or what the 33/25/34 opaque bytes mean.
Those data might contain positional or physical properties, indexes,
flags, transform values or unrelated metadata. Their gameplay role
and any per-object collision bindings remain **unverified**.

## Reproducible source-private reader

Implementation: \`src/heman_tools/physics_typed_trailer.py\`.

Use the owner's original IPA privately:

\`\`\`sh
PYTHONPATH=src python -m heman_tools.physics_typed_trailer \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/physics_typed_trailer.json
\`\`\`

The tool builds on Stage141's already-bounded main record envelope
and Stage140's archive parity/security reader. It validates complete
UTF-16 strings, accepted discriminator values, every opaque payload
size, exact declared item count and exact EOF. It never publishes
source strings, individual resource identities, raw data, coordinates,
shape filenames, candidate offsets, or any per-file hash. Only
aggregate counts and static, falsifiable capability flags are written
under ignored \`local_reports/\`.

Public tests use **20 synthetic-only cases**, covering all three
variants, mixed variants and Unicode strings, corrupt UTF-16,
unsupported types, short reads, wrong declared counts, leftover
bytes, malformed input, privacy redaction, mismatched screen packs,
duplicate ZIP members, symlinks and a wholly fabricated ZIP audit.

## What this changes—and what it does not

Unlike a permissive variable-width search, this parser does not
seek arbitrary record lengths or choose among many possible paths.
It deterministically consumes records by their serialized
discriminator and a fixed per-variant size. This is a concrete
advance in **binary-file structure**.

However, the following remain blocked:

- The numeric/boolean meaning of the variant codes.
- The opaque 33/25/34-byte payload fields.
- The separate opaque **50-byte main physics-record** sections.
- Which first-level game objects own these records and shapes.
- Runtime collision/health/damage/animation semantics.
- Actual iOS gameplay or physical Nintendo Switch parity.
- Automatic import of original geometry into the test NRO.

Next validate candidate field **types** in the per-variant payloads
against independent structural constraints; require coherence across
all original records and reject float/flag interpretations that
cannot be independently corroborated. Keep source geometry private.
