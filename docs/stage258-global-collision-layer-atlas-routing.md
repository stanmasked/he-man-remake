# Stage258 — global collision-layer atlas routing census

## Purpose

Stage057/074 and Stage257 established first-level collision-layer occupancy and alpha-mask observations. Stage258 widens the audit to every parseable map resource in both screen packs. It counts atlas names and tile IDs inside layers named collision, verifies exact source-map pair equality, and follows the original TilesetData and TextureData repository indexes to resolve atlas aliases.

The tool reads ZIP entries in memory and emits aggregate counts only. It does not export per-cell coordinates, map names, original bytes or images.

## Owner-private original-IPA findings

- 214 map files are present in each screen pack.
- 213 ordinary multilayer maps parse and are byte-identical across the two packs.
- One known special-format sky map is byte-different and excluded from the normal multilayer parser.
- 73 parseable maps contain a layer named collision, with 24,306 occupied cells.
- 23,618 occupied cells use the atlas named collision; the remaining 688 cells reference other atlas names.
- The cloud atlas is used in 11 maps; the special atlas alias is used in two maps.

The important conclusion is that a layer named collision does not imply that every occupied cell uses the collision atlas. Every atlas route must be resolved before interpreting its cells.

## Registry correction: special resolves to damage.tileset

The original TilesetData.repo maps the special atlas key to /tilesets/damage.tileset. That tileset references the specialTiles key, which is present in TextureData.repo. The alias is therefore resolved through the authoritative resource registry; the absence of a same-stem special.tileset file is not a missing resource.

A separate filename-based PNG candidate has different tile-0 alpha coverage across the two screen packs. This does not invalidate the registry mapping and does not prove the runtime texture has the same alpha data: the actual texture key is indexed in TextureData.wad. Do not use the separately named PNG as a collision mask until its relationship to the runtime WAD resource and rendering path is verified.

The complete owner-private atlas/tile frequencies, registry manifest and candidate PNG comparison are preserved in the private Stage258 Drive handoff.

## Local command

Run from the repository root with Python 3.10+:

    PYTHONPATH=src python -m heman_tools.collision_layer_atlas_inventory --ipa /secure/private/He-Man-v2.0.0.ipa --out local_reports/collision-layer-atlas-routing.json

    PYTHONPATH=src python -m unittest discover -s tests -p test_collision_layer_atlas_inventory.py -v

Public CI uses fabricated multilayer maps and resource registries only. No original IPA is loaded by CI.

## Evidence boundary

The inventory proves source-file parity, resource-registry resolution and aggregate atlas routing. It does not establish collision response, solidity, slope behavior, one-way platforms, hazards, actor ownership, coordinate scale or original gameplay parity. Registry resolution is not proof of physics semantics. All original collision semantics remain unverified, and native Switch collision import remains unauthorized until the runtime lookup and behavior are independently established.
