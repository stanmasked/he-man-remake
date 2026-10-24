# Stage259 — tileset collision-field census

## Purpose

Stage258 resolved the atlas routing used by layers named collision. Stage259 adds a private-only parser for the common tileset resource envelope and joins the aggregate map tile-ID frequencies to the corresponding tile records. The parser uses the field layout confirmed by the original runtime loader/accessor path rather than treating every field as anonymous data.

The tool writes detailed per-tile metadata only beneath ignored local_reports/. Public CI uses synthetic maps, resource registries, WAD records and tilesets; it never loads the original IPA.

## Structural field mapping

For the common format, the six leading 32-bit values are four tile dimensions followed by collision category and collision bitmask. The next 32-bit values encode an optional-name length and the number of texture layers. Each layer contains a texture reference and a tile count.

Each tile record contains rectangle coordinates and dimensions, a collision ID, two additional signed-data fields, an opacity-flag word, a shape marker, and a shape-name reference. The opacity flag is exposed as the low byte because that is what the runtime accessor reads. The parser preserves the raw word and marker rather than assigning undocumented meanings to them.

## Validation behavior

- Reject malformed lengths, unreasonable counts, invalid rectangles, truncated records and unexpected trailing bytes.
- Compare collision-related metadata across screen-med and screen-xlarge packs while allowing rectangle dimensions to differ.
- Join map tile IDs to tile records only when the resource has the supported single-layer structure.
- Report unsupported formats and out-of-range tile IDs explicitly instead of guessing.
- Keep all original per-tile names, resource values and detailed frequencies in private local reports.

## Local command

Run from the repository root with Python 3.10+:

    PYTHONPATH=src python -m heman_tools.tileset_collision_field_census --ipa /secure/private/He-Man-v2.0.0.ipa --out local_reports/tileset-collision-fields.json

    PYTHONPATH=src python -m unittest discover -s tests -p test_tileset_collision_field_census.py -v

## Evidence boundary

This stage establishes a structural mapping between serialized tile records and fields accessed by the original runtime. It does not establish what collision IDs, categories, bitmasks, S32 values, shape markers or opacity flags mean during gameplay. It does not authorize native collision import. The next step is to trace collision-map metadata lookup and tile-body generation, then compare those results with privately observed original-game behavior.
