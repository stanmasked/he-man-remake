# Stage265 — collision tile names to private geometry resources

## Original source finding

Stage264 connected Tile deserialization and its candidate collision-shape reference field in the original iOS executable. Stage265 establishes an independent cross-resource lexical join between the serialized collision tileset, geometry member names and the Level 1-1 collision map.

The two resolution packs each contain a collision tileset with 16 serialized tile records. Eleven records have a nonempty shape-reference name, and ten of those names have an exactly matching geometry resource filename. One named record does not have an exact matching filename; a similarly spelled member lacks a separator dot before the extension. The tool does not silently normalize or repair it.

For Level 1-1 specifically, the collision layer has six used tile IDs and 790 occupied cells. Three used IDs carry nonempty geometry references and all three match an exact original geometry member. The remaining three used IDs have blank shape names. No used named ID is missing its named resource.

All ten exactly matching original geometry members are byte-identical across screen-med and screen-xlarge. The Level 1-1 map bytes are also identical. This supports a resolution-independent naming relationship but does not establish whether the physical collider is actually loaded at runtime.

## Method

The owner-local tool reads the original IPA directly through bounded ZIP-entry operations. It parses the two collision tilesets and matching map files, checks atlas routing and occupied IDs, and validates every named geometry member against the exact path expected from serialized tile data. It reports aggregate counts, cross-pack byte parity, and any missing-extension anomaly without exporting resource names, image pixels, geometry data, or original member paths.

## Limitations

The exact lexical match is stronger than an arbitrary texture-alpha shape hypothesis, especially when combined with Stage264's setter/generator code evidence. It is nevertheless not proof of:

- successful runtime loading of a geometry resource;
- the type of object stored in the Tile collision-shape handle;
- how CTileMap::initializeCollision converts it into solid/slope/one-way geometry;
- whether texture alpha participates elsewhere in collision handling;
- actual original iOS gameplay collision response or Switch parity.

A malformed geometry member name remains a diagnostic issue even when a likely typo is present. No original resource is renamed or modified.

## Private CLI

From the repository root, with the user-owned IPA stored off-repository:

    PYTHONPATH=src python -m heman_tools.collision_geometry_name_link --ipa /secure/private/He-Man-v2.0.0.ipa --map MUMap1-1.map --out local_reports/stage265-level1-geometry-names.json

The report must remain in the ignored private local reports area and be backed up in the private Google Drive project folder.

## Public CI

The public workflow exercises fictional tileset records, fabricated map grids and invented geometry member files. Tests cover exact matches, a suffix-extension typo, missing matches, cross-pack changes, map divergence, basename validation and output redaction.

Next stage: trace the exact geometry resource loader's return type and how CTileMap converts the loaded shape into a physical collider. Do not use lexical relationships alone as permission to import original collision masks into native Switch physics.
