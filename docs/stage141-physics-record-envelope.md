# Stage141 — structural decoder for original iOS physics records

The owner-private iOS v2.0.0 archive contains **81 paired** physics-structure
files, with corresponding medium and extra-large binaries byte-identical.
Stage140 found only full length-prefixed UTF-16 lexical candidates.

A bounded source-private experiment now parses the **complete repeated
record envelope in all 81 files**, not merely the occurrence of text.

## Observed binary envelope

The following is an observed structural pattern, **not a full physics
format specification**:

```text
u32_le record_count
repeat record_count:
    u16_le local_label_utf16_units
    local_label_utf16le [units*2 bytes]
    opaque_payload [50 bytes]       # NOT interpreted
    u32_le following_string_count
    repeat following_string_count:
        u16_le reference_utf16_units
        reference_utf16le [units*2 bytes]
u32_le trailing_group_count
if trailing_group_count > 0:
    unknown optional trailer bytes # NOT parsed
else:
    EOF
```

The helper strictly bounds every length/count, validates all UTF-16LE
strings and fails on malformed or extra bytes following a zero-length
trailer. It does not guess that the 50-byte payload contains actual
world coordinates, engine material constants, collision category flags
or actor transforms.

### Owner-private aggregate results

| Observed structural property | Value |
|---|---:|
| File pairs whose repeated record envelope parses | **81/81** |
| Total physics records | **187** |
| Reference strings in records | **187** |
| References exactly matching a global `.shape` stem | **175** |
| Distinct exact matching shape stems | **112** |
| Files ending in a single zero trailer count | **68** |
| Files with additional unclassified trailer data | **13** |

Some records' source strings do not match shape filenames. These are
not silently dropped or reinterpreted; they may refer to other runtime
resources. Matching a `.shape` stem is still **textual evidence**, not
proof that the original runtime loads that file into a hitbox or that
the link remains valid during gameplay.

The 13 longer trailer blocks require a separate, evidence-grounded
decoder. Attempting to process those unknown trailers as joint
definitions or constraints without validating their field boundaries
would be unjustified.

## Owner-local read-only command

```sh
PYTHONPATH=src python -m heman_tools.physics_records \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/physics_record_envelope.json
```

The original archive remains locally owned. The parser returns
aggregate counts, fixed booleans and documented unknowns; it does
**not** export original strings, shape names, coordinates, parsed
geometry arrays, 50-byte payloads, trailer bytes or hashes.
Only fictional ZIPs and invented shapes appear in public GitHub
regression tests.

The tool **always** sets these to false:

- `fifty_byte_record_payload_fields_decoded`
- `nonempty_trailer_payload_fields_decoded`
- `string_means_runtime_shape_reference_proven`
- `source_game_collision_semantics_verified`
- `ready_for_switch_geometry_import`

## Next development gates

1. Independently decode and validate the nonzero trailer record
   boundaries, retaining opaque fields until understood.
2. Test hypotheses about the fixed 50-byte payload on *synthetic*
   records, then verify against original source stats privately.
3. Establish which Level1-1 objects refer to physics-structure
   resources and what it means for their animation state.
4. Derive valid player/controller/camera comparisons from an actual
   original iOS reference where possible.
5. Only after runtime-grounded ownership and coordinate transforms
   are verified should source game geometry be adapted privately to
   the independently authored Switch test engine.
